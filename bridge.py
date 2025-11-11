from web3 import Web3
from web3.providers.rpc import HTTPProvider
from web3.middleware import ExtraDataToPOAMiddleware
from datetime import datetime
import json
import pandas as pd


def connect_to(chain):
    if chain == 'source':
        api_url = f"https://api.avax-test.network/ext/bc/C/rpc"
    if chain == 'destination':
        api_url = f"https://data-seed-prebsc-1-s1.binance.org:8545/"
    if chain in ['source','destination']:
        w3 = Web3(Web3.HTTPProvider(api_url))
        w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    return w3


def get_contract_info(chain, contract_info):
    try:
        with open(contract_info, 'r')  as f:
            contracts = json.load(f)
    except Exception as e:
        print( f"Failed to read contract info\nPlease contact your instructor\n{e}" )
        return 0
    return contracts[chain]


def scan_blocks(chain, contract_info="contract_info.json"):
    if chain not in ['source','destination']:
        print( f"Invalid chain: {chain}" )
        return 0
    
    contract_data = get_contract_info(chain, contract_info)
    if not contract_data:
        return 0
    
    contract_address = contract_data['address']
    contract_abi = contract_data['abi']
    
    w3 = connect_to(chain)
    contract = w3.eth.contract(address=contract_address, abi=contract_abi)
    
    latest_block = w3.eth.block_number
    from_block = max(0, latest_block - 4)
    to_block = latest_block
    
    import os
    warden_private_key = os.getenv('PRIVATE_KEY')
    if not warden_private_key:
        print("Error: PRIVATE_KEY environment variable not set")
        return 0
    
    from eth_account import Account
    warden_account = Account.from_key(warden_private_key)
    warden_address = warden_account.address
    
    if chain == 'source':
        # 使用 web3.py 的正确方式获取事件日志
        event_filter = contract.events.Deposit.build_filter()
        event_filter.fromBlock = from_block
        event_filter.toBlock = to_block
        
        try:
            deposit_events = event_filter.deploy(w3).get_all_entries()
        except:
            # 备用方法：直接使用 getLogs
            try:
                deposit_events = w3.eth.get_logs({
                    'fromBlock': from_block,
                    'toBlock': to_block,
                    'address': contract_address,
                    'topics': [w3.keccak(text="Deposit(address,address,uint256)").hex()]
                })
                # 解析事件
                deposit_events = [contract.events.Deposit().process_log(log) for log in deposit_events]
            except Exception as e:
                print(f"No Deposit events found or error: {e}")
                deposit_events = []
        
        for event in deposit_events:
            token = event['args']['token']
            recipient = event['args']['recipient']
            amount = event['args']['amount']
            
            print(f"Found Deposit event: token={token}, recipient={recipient}, amount={amount}")
            
            dest_contract_data = get_contract_info('destination', contract_info)
            dest_w3 = connect_to('destination')
            dest_contract = dest_w3.eth.contract(
                address=dest_contract_data['address'],
                abi=dest_contract_data['abi']
            )
            
            try:
                nonce = dest_w3.eth.get_transaction_count(warden_address)
                
                wrap_txn = dest_contract.functions.wrap(
                    token,
                    recipient,
                    amount
                ).build_transaction({
                    'from': warden_address,
                    'nonce': nonce,
                    'gas': 300000,
                    'gasPrice': dest_w3.eth.gas_price
                })
                
                signed_txn = warden_account.sign_transaction(wrap_txn)
                tx_hash = dest_w3.eth.send_raw_transaction(signed_txn.rawTransaction)
                tx_receipt = dest_w3.eth.wait_for_transaction_receipt(tx_hash)
                
                print(f"Wrap transaction successful: {tx_hash.hex()}")
                
            except Exception as e:
                print(f"Error calling wrap(): {e}")
    
    elif chain == 'destination':
        # 使用相同的方法处理 Unwrap 事件
        event_filter = contract.events.Unwrap.build_filter()
        event_filter.fromBlock = from_block
        event_filter.toBlock = to_block
        
        try:
            unwrap_events = event_filter.deploy(w3).get_all_entries()
        except:
            # 备用方法
            try:
                unwrap_events = w3.eth.get_logs({
                    'fromBlock': from_block,
                    'toBlock': to_block,
                    'address': contract_address,
                    'topics': [w3.keccak(text="Unwrap(address,address,address,address,uint256)").hex()]
                })
                unwrap_events = [contract.events.Unwrap().process_log(log) for log in unwrap_events]
            except Exception as e:
                print(f"No Unwrap events found or error: {e}")
                unwrap_events = []
        
        for event in unwrap_events:
            underlying_token = event['args']['underlying_token']
            recipient = event['args']['to']
            amount = event['args']['amount']
            
            print(f"Found Unwrap event: token={underlying_token}, recipient={recipient}, amount={amount}")
            
            source_contract_data = get_contract_info('source', contract_info)
            source_w3 = connect_to('source')
            source_contract = source_w3.eth.contract(
                address=source_contract_data['address'],
                abi=source_contract_data['abi']
            )
            
            try:
                nonce = source_w3.eth.get_transaction_count(warden_address)
                
                withdraw_txn = source_contract.functions.withdraw(
                    underlying_token,
                    recipient,
                    amount
                ).build_transaction({
                    'from': warden_address,
                    'nonce': nonce,
                    'gas': 300000,
                    'gasPrice': source_w3.eth.gas_price
                })
                
                signed_txn = warden_account.sign_transaction(withdraw_txn)
                tx_hash = source_w3.eth.send_raw_transaction(signed_txn.rawTransaction)
                tx_receipt = source_w3.eth.wait_for_transaction_receipt(tx_hash)
                
                print(f"Withdraw transaction successful: {tx_hash.hex()}")
                
            except Exception as e:
                print(f"Error calling withdraw(): {e}")
