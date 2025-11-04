const fs = require('fs');
const path = require('path');

const changelogs = {
  '@sema4ai/spar-ui': '../CHANGELOG.md',
};

const getLatestReleaseChanges = (packageName) => {
  const content = fs.readFileSync(path.join(__dirname, changelogs[packageName]), 'utf-8');

  const sections = content.split(/^## /m);
  const latestSection = sections[1];

  const lines = latestSection.trim().split('\n');
  const version = lines[0].trim();

  const changes = lines
    .filter((line) => line.startsWith('- ') && !line.startsWith('- Updated dependencies'))
    .map((line) => `- ${line.trim().substring(2).split(': ')[1].trim()}`);

  return { version, changes };
};

const createReleaseFile = async () => {
  try {
    const args = process.argv.slice(2);
    const packages = JSON.parse(args[0]);

    let output = `*New version of <https://github.com/Sema4AI/agent-platform/pkgs/npm/spar-ui|Spar UI> package has been released!* :rocket:`;

    for (let i = 0; i < packages.length; i += 1) {
      const { name, version } = packages[i];

      const { version: latestVersion, changes } = getLatestReleaseChanges(name);

      if (changes.length > 0) {
        output = output + `\n\n\`"${name}": "${latestVersion}"\``;
        output = output + `\n${changes.join('\n')}`;
      }
    }

    output = output + `\n\nSee full release notes at https://github.com/Sema4AI/agent-platform/releases?q=spar-ui`;

    console.log(output);
  } catch (err) {
    console.log(err);
  }
};

createReleaseFile();
