// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

/// @title ShieldPayEscrow
/// @notice Local-demo escrow for simulated value only. The backend oracle is
///         the only caller allowed to create or resolve payment records.
contract ShieldPayEscrow {
    enum Status { NONE, LOCKED, MANUAL_REVIEW, RELEASED, REFUNDED }

    struct Escrow {
        bytes32 transactionId;
        string senderIdentity;
        string receiverIdentity;
        address payable sender;
        address payable receiver;
        uint256 amount;
        // scamScore is the immutable score snapshot taken when the payment starts.
        uint8 scamScore;
        uint8 currentScore;
        uint64 createdAt;
        uint64 expiresAt;
        Status status;
    }

    address public immutable oracle;
    mapping(bytes32 => Escrow) public escrows;
    mapping(bytes32 => bytes32[]) private receiverEscrowIds;
    mapping(bytes32 => uint8) public receiverScores;
    mapping(bytes32 => bool) private receiverHasScore;

    event EscrowCreated(
        bytes32 indexed transactionId,
        string senderIdentity,
        string receiverIdentity,
        address sender,
        address receiver,
        uint256 amount,
        uint8 scamScore,
        uint64 expiresAt
    );
    event ReceiverScoreUpdated(string receiverIdentity, uint8 previousScore, uint8 newScore);
    event EscrowReleased(bytes32 indexed transactionId, address indexed receiver, uint256 amount, uint8 scamScore);
    event EscrowRefunded(bytes32 indexed transactionId, address indexed sender, uint256 amount, uint8 scamScore);
    event EscrowManualReview(bytes32 indexed transactionId, uint64 expiredAt);

    error UnauthorizedOracle();
    error InvalidValue();
    error InvalidScore();
    error InvalidAddress();
    error DuplicateTransaction();
    error NotOpenEscrow();
    error NotExpired();
    error NotInManualReview();
    error TransferFailed();

    modifier onlyOracle() {
        if (msg.sender != oracle) revert UnauthorizedOracle();
        _;
    }

    constructor(address oracleAddress) {
        if (oracleAddress == address(0)) revert InvalidAddress();
        oracle = oracleAddress;
    }

    /// @notice Locks msg.value for one medium-risk payment. Called by backend oracle.
    function createEscrow(
        bytes32 transactionId,
        string calldata senderIdentity,
        string calldata receiverIdentity,
        address payable sender,
        address payable receiver,
        uint8 scamScore,
        uint64 expiresAt
    ) external payable onlyOracle {
        if (transactionId == bytes32(0) || escrows[transactionId].status != Status.NONE) revert DuplicateTransaction();
        if (msg.value == 0 || expiresAt <= block.timestamp) revert InvalidValue();
        if (scamScore < 50 || scamScore > 80) revert InvalidScore();
        if (sender == address(0) || receiver == address(0) || sender == receiver) revert InvalidAddress();

        escrows[transactionId] = Escrow({
            transactionId: transactionId,
            senderIdentity: senderIdentity,
            receiverIdentity: receiverIdentity,
            sender: sender,
            receiver: receiver,
            amount: msg.value,
            scamScore: scamScore,
            currentScore: scamScore,
            createdAt: uint64(block.timestamp),
            expiresAt: expiresAt,
            status: Status.LOCKED
        });
        bytes32 receiverKey = keccak256(bytes(receiverIdentity));
        receiverEscrowIds[receiverKey].push(transactionId);
        if (!receiverHasScore[receiverKey]) {
            receiverScores[receiverKey] = scamScore;
            receiverHasScore[receiverKey] = true;
        }
        emit EscrowCreated(transactionId, senderIdentity, receiverIdentity, sender, receiver, msg.value, scamScore, expiresAt);
    }

    /// @notice Authenticated oracle score update applies the same bands as backend.
    function setReceiverScore(string calldata receiverIdentity, uint8 newScore) external onlyOracle {
        if (newScore > 100) revert InvalidScore();
        bytes32 receiverKey = keccak256(bytes(receiverIdentity));
        bytes32[] storage ids = receiverEscrowIds[receiverKey];
        uint8 previousScore = receiverScores[receiverKey];
        receiverScores[receiverKey] = newScore;
        receiverHasScore[receiverKey] = true;
        for (uint256 i = 0; i < ids.length; i++) {
            Escrow storage escrow = escrows[ids[i]];
            if (escrow.status != Status.LOCKED && escrow.status != Status.MANUAL_REVIEW) continue;
            escrow.currentScore = newScore;
            if (newScore < 50) {
                escrow.status = Status.RELEASED;
                _pay(escrow.receiver, escrow.amount);
                emit EscrowReleased(escrow.transactionId, escrow.receiver, escrow.amount, newScore);
            } else if (newScore > 80) {
                escrow.status = Status.REFUNDED;
                _pay(escrow.sender, escrow.amount);
                emit EscrowRefunded(escrow.transactionId, escrow.sender, escrow.amount, newScore);
            }
        }
        emit ReceiverScoreUpdated(receiverIdentity, previousScore, newScore);
    }

    /// @notice Anyone may flag an expired hold for review; funds remain in contract.
    function markExpired(bytes32 transactionId) external {
        Escrow storage escrow = escrows[transactionId];
        if (escrow.status != Status.LOCKED) revert NotOpenEscrow();
        if (block.timestamp < escrow.expiresAt) revert NotExpired();
        escrow.status = Status.MANUAL_REVIEW;
        emit EscrowManualReview(transactionId, uint64(block.timestamp));
    }

    /// @notice Backend oracle resolves a timed-out hold by refunding its sender.
    function refundAfterReview(bytes32 transactionId) external onlyOracle {
        Escrow storage escrow = escrows[transactionId];
        if (escrow.status != Status.MANUAL_REVIEW) revert NotInManualReview();
        escrow.status = Status.REFUNDED;
        _pay(escrow.sender, escrow.amount);
        emit EscrowRefunded(transactionId, escrow.sender, escrow.amount, escrow.currentScore);
    }

    function statusOf(bytes32 transactionId) external view returns (Status) {
        return escrows[transactionId].status;
    }

    function _pay(address payable recipient, uint256 amount) private {
        (bool ok,) = recipient.call{value: amount}("");
        if (!ok) revert TransferFailed();
    }
}
