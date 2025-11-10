import eth_account
import random
import string
import json
from pathlib import Path
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware  # Necessary for POA chains


def merkle_assignment():
    """
        The only modifications you need to make to this method are to assign
        your "random_leaf_index" and uncomment the last line when you are
        ready to attempt to claim a prime. You will need to complete the
        methods called by this method to generate the proof.
    """
    # Generate the list of primes as integers
    num_of_primes = 8192
    primes = generate_primes(num_of_primes)

    # Create a version of the list of primes in bytes32 format
    leaves = convert_leaves(primes)

    # Build a Merkle tree using the bytes32 leaves as the Merkle tree's leaves
    tree = build_merkle(leaves)

    # Try multiple primes if needed
    max_attempts = 10
    for attempt in range(max_attempts):
        # Select from lower indices where more primes are unclaimed
        random_leaf_index = random.randint(20, 100)  # Focus on lower indices
        
        print(f"\n尝试 {attempt + 1}/{max_attempts}")
        print(f"Attempting to claim prime at index {random_leaf_index}: {primes[random_leaf_index]}")
        
        proof = prove_merkle(tree, random_leaf_index)

        # This is the same way the grader generates a challenge for sign_challenge()
        challenge = ''.join(random.choice(string.ascii_letters) for i in range(32))
        # Sign the challenge to prove to the grader you hold the account
        addr, sig = sign_challenge(challenge)

        if sign_challenge_verify(challenge, addr, sig):
            try:
                # Pass the leaf directly (it's already bytes32, not hashed)
                tx_hash = send_signed_msg(proof, leaves[random_leaf_index])
                
                # 检查交易是否成功
                w3 = connect_to('bsc')
                receipt = w3.eth.get_transaction_receipt(tx_hash)
                
                if receipt['status'] == 1:
                    print(f"\n🎉 成功！质数 {primes[random_leaf_index]} 已被认领！")
                    print(f"交易哈希: {tx_hash}")
                    print(f"区块号: {receipt['blockNumber']}")
                    return tx_hash
                else:
                    print(f"交易失败，尝试其他质数...")
                    continue
                    
            except Exception as e:
                print(f"错误: {e}")
                print(f"尝试其他质数...")
                continue
        else:
            print("签名验证失败")
            return None
    
    print(f"\n尝试了 {max_attempts} 次都失败了。")
    print("可能所有随机选择的质数都已被认领。")
    print("请运行 'python diagnose.py' 来找到未被认领的质数。")


def generate_primes(num_primes):
    """
        Function to generate the first 'num_primes' prime numbers
        returns list (with length n) of primes (as ints) in ascending order
    """
    primes_list = []
    candidate = 2
    
    while len(primes_list) < num_primes:
        is_prime = True
        # Check if candidate is divisible by any prime found so far
        for prime in primes_list:
            if prime * prime > candidate:
                break
            if candidate % prime == 0:
                is_prime = False
                break
        
        if is_prime:
            primes_list.append(candidate)
        
        candidate += 1
    
    return primes_list


def convert_leaves(primes_list):
    """
        Converts the leaves (primes_list) to bytes32 format
        returns list of primes where list entries are bytes32 encodings of primes_list entries
    """
    leaves = []
    
    for prime in primes_list:
        # Convert integer to bytes32 format (NO hashing here!)
        prime_bytes = int.to_bytes(prime, 32, 'big')
        leaves.append(prime_bytes)
    
    return leaves


def build_merkle(leaves):
    """
        Function to build a Merkle Tree from the list of prime numbers in bytes32 format
        Returns the Merkle tree (tree) as a list where tree[0] is the list of leaves,
        tree[1] is the parent hashes, and so on until tree[n] which is the root hash
        the root hash produced by the "hash_pair" helper function
    """
    tree = [leaves]
    
    # Build tree level by level
    while len(tree[-1]) > 1:
        current_level = tree[-1]
        next_level = []
        
        # Process pairs of nodes
        for i in range(0, len(current_level), 2):
            if i + 1 < len(current_level):
                # Hash the pair using the helper function (which sorts)
                parent = hash_pair(current_level[i], current_level[i + 1])
                next_level.append(parent)
            else:
                # Odd one out - promote to next level
                next_level.append(current_level[i])
        
        tree.append(next_level)
    
    return tree


def prove_merkle(merkle_tree, random_indx):
    """
        Takes a random_index to create a proof of inclusion for and a complete Merkle tree
        as a list of lists where index 0 is the list of leaves, index 1 is the list of
        parent hash values, up to index -1 which is the list of the root hash.
        returns a proof of inclusion as list of values
    """
    merkle_proof = []
    index = random_indx
    
    # Traverse from leaf to root (excluding the root level)
    for level in merkle_tree[:-1]:
        # Determine if we need the left or right sibling
        if index % 2 == 0:  # Current node is a left child
            # Need right sibling
            if index + 1 < len(level):
                merkle_proof.append(level[index + 1])
        else:  # Current node is a right child
            # Need left sibling
            merkle_proof.append(level[index - 1])
        
        # Move to parent level
        index = index // 2
    
    return merkle_proof


def sign_challenge(challenge):
    """
        Takes a challenge (string)
        Returns address, sig
        where address is an ethereum address and sig is a signature (in hex)
        This method is to allow the auto-grader to verify that you have
        claimed a prime
    """
    acct = get_account()

    addr = acct.address
    eth_sk = acct.key

    # Encode the message in Ethereum's standard format
    eth_encoded_msg = eth_account.messages.encode_defunct(text=challenge)
    
    # Sign the message
    eth_sig_obj = eth_account.Account.sign_message(eth_encoded_msg, private_key=eth_sk)

    return addr, eth_sig_obj.signature.hex()


def send_signed_msg(proof, random_leaf):
    """
        Takes a Merkle proof of a leaf, and that leaf (in bytes32 format)
        builds signs and sends a transaction claiming that leaf (prime)
        on the contract
    """
    chain = 'bsc'

    acct = get_account()
    address, abi = get_contract_info(chain)
    w3 = connect_to(chain)

    # Create contract instance
    contract = w3.eth.contract(address=address, abi=abi)
    
    # IMPORTANT: Get fresh nonce each time
    nonce = w3.eth.get_transaction_count(acct.address, 'pending')
    
    # Build the transaction
    # Note: Contract expects (proof, leaf) order based on ABI
    txn = contract.functions.submit(proof, random_leaf).build_transaction({
        'from': acct.address,
        'nonce': nonce,
        'gas': 500000,
        'gasPrice': w3.eth.gas_price
    })
    
    # Sign the transaction
    signed_txn = w3.eth.account.sign_transaction(txn, private_key=acct.key)
    
    # Send the transaction
    # Handle both old and new attribute names for compatibility
    raw_tx = getattr(signed_txn, 'raw_transaction', None) or getattr(signed_txn, 'rawTransaction')
    tx_hash = w3.eth.send_raw_transaction(raw_tx)
    
    # Wait for transaction receipt
    print(f"Waiting for transaction to be mined...")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    
    if receipt['status'] == 1:
        print(f"Transaction successful! Block: {receipt['blockNumber']}")
    else:
        print(f"Transaction failed!")
    
    print(f"Transaction hash: {tx_hash.hex()}")
    
    return tx_hash.hex()


# Helper functions that do not need to be modified
def connect_to(chain):
    """
        Takes a chain ('avax' or 'bsc') and returns a web3 instance
        connected to that chain.
    """
    if chain not in ['avax','bsc']:
        print(f"{chain} is not a valid option for 'connect_to()'")
        return None
    if chain == 'avax':
        api_url = f"https://api.avax-test.network/ext/bc/C/rpc"  # AVAX C-chain testnet
    else:
        api_url = f"https://data-seed-prebsc-1-s1.binance.org:8545/"  # BSC testnet
    w3 = Web3(Web3.HTTPProvider(api_url))
    # inject the poa compatibility middleware to the innermost layer
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

    return w3


def get_account():
    """
        Returns an account object recovered from the secret key
        in "sk.txt"
    """
    cur_dir = Path(__file__).parent.absolute()
    with open(cur_dir.joinpath('sk.txt'), 'r') as f:
        sk = f.readline().rstrip()
    if sk[0:2] == "0x":
        sk = sk[2:]
    return eth_account.Account.from_key(sk)


def get_contract_info(chain):
    """
        Returns a contract address and contract abi from "contract_info.json"
        for the given chain
    """
    contract_file = Path(__file__).parent.absolute() / "contract_info.json"
    if not contract_file.is_file():
        contract_file = Path(__file__).parent.parent.parent / "tests" / "contract_info.json"
    with open(contract_file, "r") as f:
        d = json.load(f)
        d = d[chain]
    return d['address'], d['abi']


def sign_challenge_verify(challenge, addr, sig):
    """
        Helper to verify signatures, verifies sign_challenge(challenge)
        the same way the grader will. No changes are needed for this method
    """
    eth_encoded_msg = eth_account.messages.encode_defunct(text=challenge)

    if eth_account.Account.recover_message(eth_encoded_msg, signature=sig) == addr:
        print(f"Success: signed the challenge {challenge} using address {addr}!")
        return True
    else:
        print(f"Failure: The signature does not verify!")
        print(f"signature = {sig}\naddress = {addr}\nchallenge = {challenge}")
        return False


def hash_pair(a, b):
    """
        The OpenZeppelin Merkle Tree Validator we use sorts the leaves
        https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/utils/cryptography/MerkleProof.sol#L217
        So you must sort the leaves as well

        Also, hash functions like keccak are very sensitive to input encoding, so the solidity_keccak function is the function to use

        Another potential gotcha, if you have a prime number (as an int) bytes(prime) will *not* give you the byte representation of the integer prime
        Instead, you must call int.to_bytes(prime,'big').
    """
    if a < b:
        return Web3.solidity_keccak(['bytes32', 'bytes32'], [a, b])
    else:
        return Web3.solidity_keccak(['bytes32', 'bytes32'], [b, a])


if __name__ == "__main__":
    merkle_assignment()