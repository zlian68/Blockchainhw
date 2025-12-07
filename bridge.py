from web3 import Web3
from web3.providers.rpc import HTTPProvider
from web3.middleware import ExtraDataToPOAMiddleware
from eth_account import Account
import json
import os
import time


def connect_to(chain):
    if chain == 'source':
        api_url = "https://api.avax-test.network/ext/bc/C/rpc"
    elif chain == 'destination':
        api_url = "https://data-seed-prebsc-1-s1.binance.org:8545/"
    else:
        raise ValueError(f"Unknown chain: {chain}")
    w3 = Web3(Web3.HTTPProvider(api_url))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    return w3


def get_contract_info(chain, contract_info):
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, contract_info)
        if os.path.exists(config_path):
            contract_info = config_path
        with open(contract_info, 'r') as f:
            contracts = json.load(f)
    except Exception as e:
        print(f"Failed to read contract info: {e}")
        return None
    return contracts[chain]


def get_warden_account():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    secret_key_files = [
        os.path.join(script_dir, 'secret_key.txt'),
        'secret_key.txt',
        './secret_key.txt'
    ]
    warden_private_key = None
    for key_file in secret_key_files:
        if os.path.exists(key_file):
            try:
                with open(key_file, 'r') as f:
                    warden_private_key = f.read().strip()
                if warden_private_key:
                    break
            except:
                continue
    if not warden_private_key:
        warden_private_key = os.getenv('PRIVATE_KEY')
    if not warden_private_key:
        print("Error: Could not find private key in secret_key.txt or PRIVATE_KEY env var")
        return None, None
    if not warden_private_key.startswith('0x'):
        warden_private_key = '0x' + warden_private_key
    warden_account = Account.from_key(warden_private_key)
    return warden_account, warden_private_key


def scan_blocks(chain, contract_info="contract_info.json"):
    if chain not in ['source', 'destination']:
        print(f"Invalid chain: {chain}")
        return
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, contract_info)
    if os.path.exists(config_path):
        contract_info = config_path
    contract_data = get_contract_info(chain, contract_info)
    if not contract_data:
        return
    contract_address = contract_data['address']
    contract_abi = contract_data['abi']
    w3 = connect_to(chain)
    contract = w3.eth.contract(address=contract_address, abi=contract_abi)
    warden_account, _ = get_warden_account()
    if not warden_account:
        return
    warden_address = warden_account.address
    latest_block = w3.eth.block_number
    from_block = max(0, latest_block - 30)
    to_block = latest_block
    
    if chain == 'source':
        deposit_events = []
        try:
            deposit_filter = contract.events.Deposit.create_filter(from_block=from_block, to_block=to_block)
            deposit_events = deposit_filter.get_all_entries()
        except:
            pass
        if not deposit_events:
            try:
                logs = w3.eth.get_logs({
                    'fromBlock': from_block,
                    'toBlock': to_block,
                    'address': contract_address
                })
                for log in logs:
                    try:
                        evt = contract.events.Deposit().process_log(log)
                        deposit_events.append(evt)
                    except:
                        pass
            except:
                pass
        dest_data = get_contract_info('destination', contract_info)
        dest_w3 = connect_to('destination')
        dest_contract = dest_w3.eth.contract(address=dest_data['address'], abi=dest_data['abi'])
        current_nonce = dest_w3.eth.get_transaction_count(warden_address, 'latest')
        for event in deposit_events:
            token = event['args']['token']
            recipient = event['args']['recipient']
            amount = event['args']['amount']
            success = False
            for attempt in range(3):
                try:
                    txn = dest_contract.functions.wrap(token, recipient, amount).build_transaction({
                        'from': warden_address,
                        'nonce': current_nonce,
                        'gas': 500000,
                        'gasPrice': int(dest_w3.eth.gas_price * 1.5),
                        'chainId': dest_w3.eth.chain_id
                    })
                    signed = warden_account.sign_transaction(txn)
                    raw = getattr(signed, 'rawTransaction', None) or signed.raw_transaction
                    tx_hash = dest_w3.eth.send_raw_transaction(raw)
                    receipt = dest_w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
                    if receipt['status'] == 1:
                        current_nonce += 1
                        success = True
                        time.sleep(2)
                        break
                except Exception as e:
                    print(f"Error wrap attempt {attempt+1}: {e}")
                    time.sleep(3)
                    current_nonce = dest_w3.eth.get_transaction_count(warden_address, 'latest')
    
    elif chain == 'destination':
        unwrap_events = []
        try:
            unwrap_filter = contract.events.Unwrap.create_filter(from_block=from_block, to_block=to_block)
            unwrap_events = unwrap_filter.get_all_entries()
        except:
            pass
        if not unwrap_events:
            try:
                logs = w3.eth.get_logs({
                    'fromBlock': from_block,
                    'toBlock': to_block,
                    'address': contract_address
                })
                for log in logs:
                    try:
                        evt = contract.events.Unwrap().process_log(log)
                        unwrap_events.append(evt)
                    except:
                        pass
            except:
                pass
        source_data = get_contract_info('source', contract_info)
        source_w3 = connect_to('source')
        source_contract = source_w3.eth.contract(address=source_data['address'], abi=source_data['abi'])
        current_nonce = source_w3.eth.get_transaction_count(warden_address, 'latest')
        for event in unwrap_events:
            underlying_token = event['args']['underlying_token']
            recipient = event['args']['to']
            amount = event['args']['amount']
            success = False
            for attempt in range(3):
                try:
                    txn = source_contract.functions.withdraw(underlying_token, recipient, amount).build_transaction({
                        'from': warden_address,
                        'nonce': current_nonce,
                        'gas': 500000,
                        'gasPrice': int(source_w3.eth.gas_price * 1.5),
                        'chainId': source_w3.eth.chain_id
                    })
                    signed = warden_account.sign_transaction(txn)
                    raw = getattr(signed, 'rawTransaction', None) or signed.raw_transaction
                    tx_hash = source_w3.eth.send_raw_transaction(raw)
                    receipt = source_w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
                    if receipt['status'] == 1:
                        current_nonce += 1
                        success = True
                        time.sleep(2)
                        break
                except Exception as e:
                    print(f"Error withdraw attempt {attempt+1}: {e}")
                    time.sleep(3)
                    current_nonce = source_w3.eth.get_transaction_count(warden_address, 'latest')
