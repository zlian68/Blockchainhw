// SPDX-License-Identifier: MIT
pragma solidity ^0.8.17;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/AccessControl.sol";
import "./BridgeToken.sol";

contract Destination is AccessControl {
  bytes32 public constant WARDEN_ROLE = keccak256("BRIDGE_WARDEN_ROLE");
  bytes32 public constant CREATOR_ROLE = keccak256("CREATOR_ROLE");

  mapping( address => address) public underlying_tokens;
	mapping( address => address) public wrapped_tokens;
	address[] public tokens;

  event Creation( address indexed underlying_token, address indexed wrapped_token );
	event Wrap( address indexed underlying_token, address indexed wrapped_token, address indexed to, uint256 amount );
	event Unwrap( address indexed underlying_token, address indexed wrapped_token, address frm, address indexed to, uint256 amount );

	constructor( address admin ) {        
    _grantRole(DEFAULT_ADMIN_ROLE, admin);
    _grantRole(CREATOR_ROLE, admin);
    _grantRole(WARDEN_ROLE, admin);
  }

	function wrap(address _underlying_token, address _recipient, uint256 _amount ) public onlyRole(WARDEN_ROLE) {
		// Look up the wrapped token address corresponding to the underlying token
    address wrappedTokenAddress = wrapped_tokens[_underlying_token];
		
    // Ensure the token has been registered/created
    require(wrappedTokenAddress != address(0), "Destination: Underlying token not supported");

    // Call the mint function on the BridgeToken contract.
    // This works because this Destination contract holds the MINTER_ROLE on that BridgeToken.
    BridgeToken(wrappedTokenAddress).mint(_recipient, _amount);
		
    // Emit the Wrap event
    emit Wrap(_underlying_token, wrappedTokenAddress, _recipient, _amount);
	}

	function unwrap(address _wrapped_token, address _recipient, uint256 _amount ) public {
		// Look up the underlying token address corresponding to the wrapped token
    address underlyingTokenAddress = underlying_tokens[_wrapped_token];
		
    // Ensure this is a valid, registered wrapped token
    require(underlyingTokenAddress != address(0), "Destination: Not a registered wrapped token");

    // Burn the tokens from the user (msg.sender) who called this function
    // See detailed explanation below for why this works without 'approve'
    BridgeToken(_wrapped_token).burnFrom(msg.sender, _amount);
		
    // Emit the Unwrap event
    emit Unwrap(underlyingTokenAddress, _wrapped_token, msg.sender, _recipient, _amount);
	}

	function createToken(address _underlying_token, string memory name, string memory symbol ) public onlyRole(CREATOR_ROLE) returns(address) {
		// Ensure this underlying token has not been registered before
    require(wrapped_tokens[_underlying_token] == address(0), "Destination: Token already registered");

		// Deploy a new BridgeToken contract
    // Pass 'address(this)' as the 'admin'
    BridgeToken newBridgeToken = new BridgeToken(_underlying_token, name, symbol, address(this));
		
    // Get the address of the newly deployed contract
    address wrappedTokenAddress = address(newBridgeToken);

		// Save the references in the mappings
		wrapped_tokens[_underlying_token] = wrappedTokenAddress;
		underlying_tokens[wrappedTokenAddress] = _underlying_token;
		tokens.push(wrappedTokenAddress);

    // Emit the Creation event
		emit Creation(_underlying_token, wrappedTokenAddress);
		
    // Return the new token's address
    return wrappedTokenAddress;
	}
}
