const assert = require('node:assert/strict');
const { ethers } = require('hardhat');

describe('ShieldPayEscrow', function () {
  let contract;
  let oracle;
  let maya;
  let arjun;
  let shop;
  const value = ethers.parseEther('0.01');
  const expiry = async () => BigInt((await ethers.provider.getBlock('latest')).timestamp + 600);

  beforeEach(async function () {
    [oracle, maya, arjun, shop] = await ethers.getSigners();
    const Factory = await ethers.getContractFactory('ShieldPayEscrow');
    contract = await Factory.deploy(oracle.address);
    await contract.waitForDeployment();
  });

  async function create(id, score = 65, sender = maya) {
    return contract.connect(oracle).createEscrow(
      ethers.id(id), sender === maya ? 'maya' : 'arjun', 'business', sender.address, shop.address,
      score, await expiry(), { value },
    );
  }

  it('restricts escrow creation and score updates to the oracle', async function () {
    await assert.rejects(contract.connect(maya).createEscrow(
      ethers.id('unauthorized'), 'maya', 'business', maya.address, shop.address, 65, await expiry(), { value },
    ));
    await assert.rejects(contract.connect(maya).setReceiverScore('business', 35));
  });

  it('locks at the initial score and releases when the score falls below 50', async function () {
    await create('release-case');
    const locked = await contract.escrows(ethers.id('release-case'));
    assert.equal(locked.status, 1n);
    assert.equal(locked.scamScore, 65n);
    const before = await ethers.provider.getBalance(shop.address);
    await contract.connect(oracle).setReceiverScore('business', 49);
    const after = await ethers.provider.getBalance(shop.address);
    assert.equal(after - before, value);
    assert.equal(await contract.statusOf(ethers.id('release-case')), 3n);
    const released = await contract.escrows(ethers.id('release-case'));
    assert.equal(released.scamScore, 65n, 'creation-time score snapshot is retained');
    assert.equal(released.currentScore, 49n, 'latest oracle score is stored separately');
    await assert.rejects(contract.connect(oracle).refundAfterReview(ethers.id('release-case')));
  });

  it('refunds sender when score rises above 80 and does not pay receiver', async function () {
    await create('refund-case', 80);
    const mayaBefore = await ethers.provider.getBalance(maya.address);
    const shopBefore = await ethers.provider.getBalance(shop.address);
    await contract.connect(oracle).setReceiverScore('business', 81);
    assert.equal(await ethers.provider.getBalance(maya.address), mayaBefore + value);
    assert.equal(await ethers.provider.getBalance(shop.address), shopBefore);
    assert.equal(await contract.statusOf(ethers.id('refund-case')), 4n);
    await assert.rejects(contract.connect(oracle).setReceiverScore('business', 35).then(() => contract.connect(oracle).refundAfterReview(ethers.id('refund-case'))));
  });

  it('keeps scores 50 and 80 locked, then safely reviews and refunds after expiry', async function () {
    await create('lower-middle', 50, maya);
    await create('upper-middle', 80, arjun);
    await contract.connect(oracle).setReceiverScore('business', 50);
    assert.equal(await contract.statusOf(ethers.id('lower-middle')), 1n);
    assert.equal(await contract.statusOf(ethers.id('upper-middle')), 1n);
    const ids = [ethers.id('lower-middle'), ethers.id('upper-middle')];
    await ethers.provider.send('evm_increaseTime', [700]);
    await ethers.provider.send('evm_mine', []);
    for (const id of ids) {
      await contract.markExpired(id);
      assert.equal(await contract.statusOf(id), 2n);
      await contract.connect(oracle).refundAfterReview(id);
      assert.equal(await contract.statusOf(id), 4n);
      await assert.rejects(contract.connect(oracle).refundAfterReview(id));
    }
  });

  it('rejects invalid score, duplicate IDs and non-escrow risk bands', async function () {
    await assert.rejects(create('too-safe', 49));
    await assert.rejects(create('too-risky', 81));
    await create('unique');
    await assert.rejects(create('unique'));
    await assert.rejects(contract.connect(oracle).setReceiverScore('business', 101));
  });
});
