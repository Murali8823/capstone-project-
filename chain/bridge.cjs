const fs = require('node:fs');
const path = require('node:path');
const { ethers } = require('ethers');

const root = path.join(__dirname, '..');
const configPath = path.join(root, 'backend', 'chain_config.json');
const action = process.argv[2];
const argument = process.argv[3] || '{}';
const input = action === 'status' && !argument.startsWith('{')
  ? { transaction_id: argument }
  : JSON.parse(argument);

async function main() {
  if (!fs.existsSync(configPath)) throw new Error('Contract is not deployed; run npm run chain:deploy first.');
  const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
  const rpc = process.env.SHIELDPAY_CHAIN_RPC_URL || 'http://127.0.0.1:8545';
  const provider = new ethers.JsonRpcProvider(rpc);
  const oracle = await provider.getSigner(0);
  const contract = new ethers.Contract(config.address, config.abi, oracle);
  const ids = ['maya', 'arjun', 'riya', 'scammer', 'business'];
  const wallets = {};
  for (let index = 0; index < ids.length; index++) wallets[ids[index]] = await (await provider.getSigner(index + 1)).getAddress();
  if (action === 'inspect') {
    return output({ connected: true, network: config.network, chainId: config.chainId, address: config.address, oracle: await oracle.getAddress(), wallets });
  }
  if (action === 'status') {
    const id = ethers.keccak256(ethers.toUtf8Bytes(input.transaction_id));
    const row = await contract.escrows(id);
    const names = ['NONE', 'LOCKED', 'MANUAL_REVIEW', 'RELEASED', 'REFUNDED'];
    const contractBalance = await provider.getBalance(config.address);
    output({ transactionId: input.transaction_id, status: names[Number(row.status)], amountWei: row.amount.toString(),
      scoreAtCreation: Number(row.scamScore), currentScore: Number(row.currentScore), sender: row.sender,
      receiver: row.receiver, contractBalanceWei: contractBalance.toString() });
    await provider.destroy();
    return;
  }
  if (action === 'reset') {
    const receipts = [];
    for (const [receiverId, safeScore] of [['business', 90], ['business', 65], ['scammer', 90], ['scammer', 95]]) {
      const tx = await contract.setReceiverScore(receiverId, safeScore);
      const receipt = await tx.wait();
      receipts.push({ receiverId, score: safeScore, txHash: receipt.hash, blockNumber: receipt.blockNumber });
    }
    output({ txHash: receipts[receipts.length - 1].txHash, status: 1, receipts, events: [] });
    await provider.destroy();
    return;
  }
  let tx;
  if (action === 'create') {
    const amount = BigInt(input.amount_paise) * 10_000_000_000n;
    const txid = ethers.keccak256(ethers.toUtf8Bytes(input.transaction_id));
    const expiry = BigInt(Math.floor(Date.parse(input.expires_at) / 1000));
    tx = await contract.createEscrow(txid, input.sender_id, input.receiver_id,
      wallets[input.sender_id], wallets[input.receiver_id], Number(input.score), expiry, { value: amount });
  } else if (action === 'score') {
    tx = await contract.setReceiverScore(input.receiver_id, Number(input.score));
  } else if (action === 'expire') {
    const id = ethers.keccak256(ethers.toUtf8Bytes(input.transaction_id));
    const row = await contract.escrows(id);
    if (row.status === 2n) return output({ txHash: null, blockNumber: null, status: 1, already: true, events: [] });
    if (row.status !== 1n) throw new Error('Escrow is not open for timeout review.');
    tx = await contract.markExpired(id);
  } else if (action === 'refund') {
    const id = ethers.keccak256(ethers.toUtf8Bytes(input.transaction_id));
    const row = await contract.escrows(id);
    if (row.status === 4n) return output({ txHash: null, blockNumber: null, status: 1, already: true, events: [] });
    if (row.status !== 2n) throw new Error('Escrow is not awaiting manual review.');
    tx = await contract.refundAfterReview(id);
  } else {
    throw new Error(`Unsupported chain action: ${action}`);
  }
  const receipt = await tx.wait();
  const events = [];
  for (const log of receipt.logs) {
    try {
      const parsed = contract.interface.parseLog(log);
      if (parsed) events.push({ name: parsed.name, args: normalize(parsed.args) });
    } catch { /* ignore logs from unrelated contracts */ }
  }
  output({ txHash: receipt.hash, blockNumber: receipt.blockNumber, status: receipt.status, events });
  await provider.destroy();
}

function normalize(value) {
  if (typeof value === 'bigint') return value.toString();
  if (Array.isArray(value)) return value.map(normalize);
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).filter(([key]) => !/^\d+$/.test(key)).map(([key, item]) => [key, normalize(item)]));
  return value;
}
function output(value) { process.stdout.write(`${JSON.stringify(value)}\n`); }

main().catch((error) => {
  process.stderr.write(`${error.shortMessage || error.message || error}\n`);
  process.exitCode = 1;
});
