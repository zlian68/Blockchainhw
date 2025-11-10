#!/bin/python
import hashlib
import os
import random


def mine_block(k, prev_hash, transactions):
    """
        k - Number of trailing zeros in the binary representation (integer)
        prev_hash - the hash of the previous block (bytes)
        transactions - a set of "transactions," i.e., data to be included in this block (list of strings)

        Complete this function to find a nonce such that 
        sha256( prev_hash + transactions + nonce )
        has k trailing zeros in its *binary* representation
    """
    if not isinstance(k, int) or k < 0:
        print("mine_block expects positive integer")
        return b'\x00'

    # Combine transactions into a single bytes object
    transactions_bytes = ''.join(transactions).encode('utf-8')
    
    # Start with nonce = 0 and increment until we find a valid hash
    nonce = 0
    
    while True:
        # Convert nonce to bytes
        nonce_bytes = nonce.to_bytes((nonce.bit_length() + 7) // 8 or 1, 'big')
        
        # Combine prev_hash + transactions + nonce
        block_content = prev_hash + transactions_bytes + nonce_bytes
        
        # Calculate SHA-256 hash
        block_hash = hashlib.sha256(block_content).digest()
        
        # Convert hash to integer to check trailing zeros in binary
        hash_int = int.from_bytes(block_hash, 'big')
        
        # Check if the last k bits are all zeros
        if hash_int % (2 ** k) == 0:
            # Found a valid nonce!
            assert isinstance(nonce_bytes, bytes), 'nonce should be of type bytes'
            return nonce_bytes
        
        nonce += 1


def get_random_lines(filename, quantity):
    """
    This is a helper function to get the quantity of lines ("transactions")
    as a list from the filename given. 
    Do not modify this function
    """
    lines = []
    with open(filename, 'r') as f:
        for line in f:
            lines.append(line.strip())

    random_lines = []
    for x in range(quantity):
        random_lines.append(lines[random.randint(0, quantity - 1)])
    return random_lines


if __name__ == '__main__':
    filename = "bitcoin_text.txt"
    num_lines = 10
    diff = 20

    prev_hash = hashlib.sha256(b"previous block").digest()
    
    transactions = get_random_lines(filename, num_lines)
    print(f"Mining with difficulty {diff}...")
    
    nonce = mine_block(diff, prev_hash, transactions)
    
    print(f"Found nonce: {nonce.hex()}")
