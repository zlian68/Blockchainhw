from web3 import Web3
from web3.providers.rpc import HTTPProvider
from web3.middleware import ExtraDataToPOAMiddleware
from eth_account import Account
import json
import os


def connect_to(chain):
    """Connect to the appropriate blockchain"""
    if chain == 'source':
        api_url = "https://api.avax-test.network/ext/bc/C/rpc"  # Avalanche Fuji Testnet
    elif chain == 'destination':
        api_url = "https://data-seed-prebsc-1-s1.binance.org:8545/"  # BSC Testnet
    else:
        raise ValueError(f"Unknown chain: {chain}")
    
    w3 = Web3(Web3.HTTPProvider(api_url))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    return w3


def get_contract_info(chain, contract_info):
    """Load contract info from JSON file"""
    try:
        with open(contract_info, 'r') as f:
            contracts = json.load(f)
    except Exception as e:
        print(f"Failed to read contract info: {e}")
        return None
    return contracts[chain]


def get_warden_account():
    """Get the warden account from private key"""
    # Try reading from secret_key.txt first
    secret_key_files = ['secret_key.txt', './secret_key.txt', '../secret_key.txt']
    warden_private_key = None
    
    for key_file in secret_key_files:
        if os.path.exists(key_file):
            try:
                with open(key_file, 'r') as f:
                    warden_private_key = f.read().strip()
                break
            except:
                continue
    
    # Fall back to environment variable
    if not warden_private_key:
        warden_private_key = os.getenv('PRIVATE_KEY')
    
    if not warden_private_key:
        print("Error: Could not find private key in secret_key.txt or PRIVATE_KEY env var")
        return None, None
    
    # Add 0x prefix if not present
    if not warden_private_key.startswith('0x'):
        warden_private_key = '0x' + warden_private_key
    
    warden_account = Account.from_key(warden_private_key)
    return warden_account, warden_private_key


def scan_blocks(chain, contract_info="contract_info.json"):
    """
    Scan for bridge events and execute cross-chain transactions.
    
    When scanning 'source' chain: Look for Deposit events -> call wrap() on destination
    When scanning 'destination' chain: Look for Unwrap events -> call withdraw() on source
    """
    if chain not in ['source', 'destination']:
        print(f"Invalid chain: {chain}")
        return
    
    # Get contract info
    contract_data = get_contract_info(chain, contract_info)
    if not contract_data:
        return
    
    contract_address = contract_data['address']
    contract_abi = contract_data['abi']
    
    # Connect to blockchain
    w3 = connect_to(chain)
    contract = w3.eth.contract(address=contract_address, abi=contract_abi)
    
    # Get warden account
    warden_account, warden_private_key = get_warden_account()
    if not warden_account:
        return
    warden_address = warden_account.address
    
    # Determine block range (scan last 5 blocks)
    latest_block = w3.eth.block_number
    from_block = max(0, latest_block - 5)
    to_block = latest_block
    
    print(f"Scanning {chain} chain from block {from_block} to {to_block}")
    print(f"Contract address: {contract_address}")
    print(f"Warden address: {warden_address}")
    
    if chain == 'source':
        # Look for Deposit events on source chain
        process_deposit_events(w3, contract, from_block, to_block, 
                               warden_account, contract_info)
    
    elif chain == 'destination':
        # Look for Unwrap events on destination chain
        process_unwrap_events(w3, contract, from_block, to_block,
                              warden_account, contract_info)


def process_deposit_events(w3, contract, from_block, to_block, warden_account, contract_info):
    """
    Process Deposit events from source chain.
    For each Deposit, call wrap() on destination chain.
    """
    warden_address = warden_account.address
    
    try:
        # Try using get_logs with event signature
        deposit_filter = contract.events.Deposit.create_filter(
            from_block=from_block,
            to_block=to_block
        )
        deposit_events = deposit_filter.get_all_entries()
    except Exception as e:
        print(f"Error getting Deposit events with filter: {e}")
        # Fallback: try get_logs directly
        try:
            event_signature = w3.keccak(text="Deposit(address,address,uint256)")
            logs = w3.eth.get_logs({
                'fromBlock': from_block,
                'toBlock': to_block,
                'address': contract.address,
                'topics': [event_signature]
            })
            deposit_events = [contract.events.Deposit().process_log(log) for log in logs]
        except Exception as e2:
            print(f"Error with fallback method: {e2}")
            deposit_events = []
    
    print(f"Found {len(deposit_events)} Deposit events")
    
    for event in deposit_events:
        token = event['args']['token']
        recipient = event['args']['recipient']
        amount = event['args']['amount']
        
        print(f"Processing Deposit: token={token}, recipient={recipient}, amount={amount}")
        
        # Call wrap() on destination chain
        try:
            dest_contract_data = get_contract_info('destination', contract_info)
            dest_w3 = connect_to('destination')
            dest_contract = dest_w3.eth.contract(
                address=dest_contract_data['address'],
                abi=dest_contract_data['abi']
            )
            
            nonce = dest_w3.eth.get_transaction_count(warden_address)
            gas_price = dest_w3.eth.gas_price
            
            wrap_txn = dest_contract.functions.wrap(
                token,      # _underlying_token (the token address on source chain)
                recipient,  # _recipient
                amount      # _amount
            ).build_transaction({
                'from': warden_address,
                'nonce': nonce,
                'gas': 500000,
                'gasPrice': gas_price,
                'chainId': dest_w3.eth.chain_id
            })
            
            signed_txn = warden_account.sign_transaction(wrap_txn)
            # Handle both old and new web3.py versions
            raw_tx = getattr(signed_txn, 'rawTransaction', None) or signed_txn.raw_transaction
            tx_hash = dest_w3.eth.send_raw_transaction(raw_tx)
            print(f"Wrap transaction sent: {tx_hash.hex()}")
            
            tx_receipt = dest_w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            print(f"Wrap transaction confirmed in block {tx_receipt['blockNumber']}")
            
        except Exception as e:
            print(f"Error calling wrap(): {e}")


def process_unwrap_events(w3, contract, from_block, to_block, warden_account, contract_info):
    """
    Process Unwrap events from destination chain.
    For each Unwrap, call withdraw() on source chain.
    
    Unwrap event signature: Unwrap(address indexed underlying_token, address indexed wrapped_token, 
                                   address frm, address indexed to, uint256 amount)
    """
    warden_address = warden_account.address
    
    try:
        # Try using get_logs with event filter
        unwrap_filter = contract.events.Unwrap.create_filter(
            from_block=from_block,
            to_block=to_block
        )
        unwrap_events = unwrap_filter.get_all_entries()
    except Exception as e:
        print(f"Error getting Unwrap events with filter: {e}")
        # Fallback: try get_logs directly
        try:
            event_signature = w3.keccak(text="Unwrap(address,address,address,address,uint256)")
            logs = w3.eth.get_logs({
                'fromBlock': from_block,
                'toBlock': to_block,
                'address': contract.address,
                'topics': [event_signature]
            })
            unwrap_events = [contract.events.Unwrap().process_log(log) for log in logs]
        except Exception as e2:
            print(f"Error with fallback method: {e2}")
            unwrap_events = []
    
    print(f"Found {len(unwrap_events)} Unwrap events")
    
    for event in unwrap_events:
        # Unwrap event args: underlying_token, wrapped_token, frm, to, amount
        underlying_token = event['args']['underlying_token']
        recipient = event['args']['to']  # 'to' is the recipient on source chain
        amount = event['args']['amount']
        
        print(f"Processing Unwrap: underlying_token={underlying_token}, recipient={recipient}, amount={amount}")
        
        # Call withdraw() on source chain
        try:
            source_contract_data = get_contract_info('source', contract_info)
            source_w3 = connect_to('source')
            source_contract = source_w3.eth.contract(
                address=source_contract_data['address'],
                abi=source_contract_data['abi']
            )
            
            nonce = source_w3.eth.get_transaction_count(warden_address)
            gas_price = source_w3.eth.gas_price
            
            withdraw_txn = source_contract.functions.withdraw(
                underlying_token,  # _token (the original token on source chain)
                recipient,         # _recipient
                amount             # _amount
            ).build_transaction({
                'from': warden_address,
                'nonce': nonce,
                'gas': 500000,
                'gasPrice': gas_price,
                'chainId': source_w3.eth.chain_id
            })
            
            signed_txn = warden_account.sign_transaction(withdraw_txn)
            # Handle both old and new web3.py versions
            raw_tx = getattr(signed_txn, 'rawTransaction', None) or signed_txn.raw_transaction
            tx_hash = source_w3.eth.send_raw_transaction(raw_tx)
            print(f"Withdraw transaction sent: {tx_hash.hex()}")
            
            tx_receipt = source_w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            print(f"Withdraw transaction confirmed in block {tx_receipt['blockNumber']}")
            
        except Exception as e:
            print(f"Error calling withdraw(): {e}")