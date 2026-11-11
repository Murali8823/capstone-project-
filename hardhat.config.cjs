require('@nomicfoundation/hardhat-ethers');
const { subtask } = require('hardhat/config');
const { TASK_COMPILE_SOLIDITY_GET_SOLC_BUILD } = require('hardhat/builtin-tasks/task-names');

// Use the pinned npm solc package so builds do not fetch a compiler at runtime.
subtask(TASK_COMPILE_SOLIDITY_GET_SOLC_BUILD, async ({ solcVersion }, _hre, runSuper) => {
  if (solcVersion === '0.8.28') {
    return {
      compilerPath: require.resolve('solc/soljson.js'),
      isSolcJs: true,
      version: solcVersion,
      longVersion: require('solc').version(),
    };
  }
  return runSuper();
});

module.exports = {
  solidity: '0.8.28',
  networks: {
    hardhat: { chainId: 31337 },
    localhost: { url: 'http://127.0.0.1:8545', chainId: 31337 },
  },
  paths: { sources: './contracts', tests: './test/contract', cache: './cache', artifacts: './artifacts' },
};
