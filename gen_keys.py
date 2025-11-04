from web3 import Web3
from eth_account.messages import encode_defunct
import eth_account
import os

def sign_message(challenge, filename="secret_key.txt"):
    """
    challenge - byte string
    filename - filename of the file that contains your account secret key
    To pass the tests, your signature must verify, and the account you use
    must have testnet funds on both the bsc and avalanche test networks.
    """
    # Read the private key from file
    with open(filename, "r") as f:
        key = f.readline().strip()
    assert(len(key) > 0), "Your account secret_key.txt is empty"

    w3 = Web3()
    
    # Encode the challenge message
    message = encode_defunct(challenge)

    # Recover account information from private key
    acct = eth_account.Account.from_key(key)
    eth_addr = acct.address
    
    # Sign the message
    signed_message = eth_account.Account.sign_message(message, private_key=key)
  
    # Verify the signature
    assert eth_account.Account.recover_message(message, signature=signed_message.signature.hex()) == eth_addr, f"Failed to sign message properly"

    # Return signed_message and account address
    return signed_message, eth_addr


if __name__ == "__main__":
    # Test the function
    for i in range(4):
        challenge = os.urandom(64)
        sig, addr = sign_message(challenge=challenge)
        print(addr)
