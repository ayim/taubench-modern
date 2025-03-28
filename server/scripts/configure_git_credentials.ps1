# Function to configure Poetry for a given repository
function Configure-PoetryForRepo {
    param (
        [string]$repo_url
    )
    $repo_name = $repo_url -replace 'https://github.com/([^/]+)/([^/]+)\.git', '$1/$2'

    poetry config "repositories.$repo_name" $repo_url
    poetry config "http-basic.$repo_name" $env:GIT_USERNAME $env:GIT_TOKEN
}

# Read the pyproject.toml file and find all dependencies with a git source
Get-Content pyproject.toml | Select-String 'git = "https://github.com/' | ForEach-Object {
    $repo_url = $_.Line -replace '.*git = "(https://github.com/[^"]+)".*', '$1'
    Configure-PoetryForRepo $repo_url
}
