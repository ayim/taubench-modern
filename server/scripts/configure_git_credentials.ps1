
param (
    [string]$GIT_USERNAME,
    [string]$GIT_TOKEN
)

function Configure-PoetryForRepo {
    param (
        [string]$repoUrl
    )
    $repoName = $repoUrl -replace 'https://github.com/([^/]+)/([^/]+).git', '$1/$2'
    poetry config repositories.$repoName $repoUrl
    poetry config http-basic.$repoName $GIT_USERNAME $GIT_TOKEN
}

# Read the pyproject.toml file and find all dependencies with a git source
$pyprojectContent = Get-Content -Path "pyproject.toml"
$gitDependencies = $pyprojectContent | Select-String -Pattern 'git = "https://github.com/' -AllMatches

foreach ($match in $gitDependencies.Matches) {
    $repoUrl = $match.Value -replace '.*git = "(https://github.com/[^"]+)".*', '$1'
    Configure-PoetryForRepo -repoUrl $repoUrl
}