const fs = require('node:fs');
const path = require('node:path');
const { ethers, artifacts, network } = require('hardhat');

async function main() {
  const [oracle] = await ethers.getSigners();
  const Factory = await ethers.getContractFactory('ShieldPayEscrow');
  const escrow = await Factory.deploy(oracle.address);
  await escrow.waitForDeployment();
  const artifact = await artifacts.readArtifact('ShieldPayEscrow');
  const deployment = {
    network: network.name,
    chainId: Number((await ethers.provider.getNetwork()).chainId),
    address: await escrow.getAddress(),
    oracle: oracle.address,
    abi: artifact.abi,
    deployedAt: new Date().toISOString(),
  };
  const destination = path.join(__dirname, '..', 'backend', 'chain_config.json');
  fs.writeFileSync(destination, `${JSON.stringify(deployment, null, 2)}\n`);
  console.log(JSON.stringify({ network: deployment.network, chainId: deployment.chainId, address: deployment.address, oracle: deployment.oracle, config: destination }, null, 2));
}

main().catch((error) => { console.error(error); process.exitCode = 1; });
