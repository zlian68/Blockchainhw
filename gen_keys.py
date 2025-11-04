from web3 import Web3
from eth_account import Account
from eth_account.messages import encode_defunct
import os

def get_keys(challenge):
    """
    Generate or load an Ethereum account, sign the challenge, 
    and return the address and signature.
    
    Args:
        challenge (str or bytes): The message to sign
        
    Returns:
        tuple: (eth_address, signature) where
            - eth_address is a string starting with '0x'
            - signature is a string starting with '0x'
    """
    
    # Initialize Web3
    w3 = Web3()
    
    # File to store your private key
    key_file = "secret_key.txt"
    
    # Check if we already have a private key saved
    if os.path.exists(key_file):
        # Load existing private key
        with open(key_file, 'r') as f:
            private_key = f.read().strip()
        acct = Account.from_key(private_key)
    else:
        # Create a new account
        acct = Account.create()
        private_key = acct.key.hex()
        
        # Save the private key for future use
        with open(key_file, 'w') as f:
            f.write(private_key)
        
        print("=" * 60)
        print("NEW ACCOUNT CREATED!")
        print("=" * 60)
        print(f"Address: {acct.address}")
        print(f"Private Key: {private_key}")
        print("\n" + "!" * 60)
        print("IMPORTANT: Get testnet tokens from these faucets:")
        print("!" * 60)
        print(f"BSC Faucet: https://testnet.bnbchain.org/faucet-smart")
        print(f"Avalanche Faucet: https://faucet.avax.network/")
        print("\nYour address is the SAME on both networks!")
        print("=" * 60)
    
    # Get the Ethereum address
    eth_address = acct.address
    
    # Handle both string and bytes challenge
    if isinstance(challenge, bytes):
        message = encode_defunct(challenge)
    else:
        message = encode_defunct(text=challenge)
    
    # Sign the message
    signed_message = w3.eth.account.sign_message(message, private_key=private_key)
    
    # Extract the signature as hex string
    signature = signed_message.signature.hex()
    
    return eth_address, signature


def main():
    """
    Test the get_keys function
    """
    print("\nTesting get_keys() function...\n")
    
    # Test with a string challenge
    test_challenge = "Test message for signing"
    address, sig = get_keys(test_challenge)
    
    print(f"Address: {address}")
    print(f"Signature: {sig[:66]}...")  # Show first part of signature
    
    # Verify the signature
    message = encode_defunct(text=test_challenge)
    recovered_address = Account.recover_message(message, signature=sig)
    
    print(f"\nVerification:")
    print(f"Signature valid: {address == recovered_address}")
    
    # Test with bytes challenge
    print("\nTesting with bytes challenge...")
    bytes_challenge = b"Random bytes message"
    address2, sig2 = get_keys(bytes_challenge)
    
    message2 = encode_defunct(bytes_challenge)
    recovered_address2 = Account.recover_message(message2, signature=sig2)
    print(f"Signature valid: {address2 == recovered_address2}")
    
    print("\n" + "=" * 60)
    print("NEXT STEPS:")
    print("=" * 60)
    print("1. Note your address above")
    print("2. Go to BSC faucet and request testnet BNB")
    print("3. Go to Avalanche faucet and request testnet AVAX")
    print("4. Check your balances:")
    print(f"   BSC: https://testnet.bscscan.com/address/{address}")
    print(f"   AVAX: https://testnet.snowtrace.io/address/{address}")
    print("=" * 60)


if __name__ == "__main__":
    main()