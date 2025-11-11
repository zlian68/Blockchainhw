// SPDX-License-Identifier: MIT
pragma solidity ^0.8.17;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/AccessControl.sol";

contract Source is AccessControl {
    bytes32 public constant ADMIN_ROLE = keccak256("ADMIN_ROLE");
    bytes32 public constant WARDEN_ROLE = keccak256("BRIDGE_WARDEN_ROLE");
	mapping( address => bool) public approved;
	address[] public tokens;

	event Deposit( address indexed token, address indexed recipient, uint256 amount );
	event Withdrawal( address indexed token, address indexed recipient, uint256 amount );
	event Registration( address indexed token );

    constructor( address admin ) {
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(ADMIN_ROLE, admin);
        _grantRole(WARDEN_ROLE, admin);

    }

	function deposit(address _token, address _recipient, uint256 _amount ) public {
		// 1. Check if the token has been registered
		require(approved[_token], "Token not registered");
		
		// 2. Use transferFrom to pull tokens from user's account into the contract
		// User must first call token.approve(address(this), amount)
		IERC20(_token).transferFrom(msg.sender, address(this), _amount);
		
		// 3. Emit Deposit event so bridge operator knows to mint tokens on destination side
		emit Deposit(_token, _recipient, _amount);
	}

	function withdraw(address _token, address _recipient, uint256 _amount ) onlyRole(WARDEN_ROLE) public {
		// 1. Permission check is already done by onlyRole(WARDEN_ROLE) modifier
		
		// 2. Use transfer to push tokens to the recipient
		IERC20(_token).transfer(_recipient, _amount);
		
		// 3. Emit Withdrawal event
		emit Withdrawal(_token, _recipient, _amount);
	}

	function registerToken(address _token) onlyRole(ADMIN_ROLE) public {
		// 1. Permission check is already done by onlyRole(ADMIN_ROLE) modifier
		
		// 2. Check that the token has not already been registered
		require(!approved[_token], "Token already registered");
		
		// 3. Add the token address to the list of registered tokens
		approved[_token] = true;
		tokens.push(_token);
		
		// 4. Emit Registration event
		emit Registration(_token);
	}


}
