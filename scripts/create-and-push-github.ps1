$ErrorActionPreference = "Stop"

$RepoName = "desktop-pet"
$Description = "Windows desktop pet with Pomodoro, voice chat, squishy drop animation, and local time tracking."

function Get-GitHubCredential {
    $inputText = "protocol=https`nhost=github.com`n`n"
    $filled = $inputText | git credential fill
    $credential = @{}
    foreach ($line in $filled) {
        if ($line -match "^(.*?)=(.*)$") {
            $credential[$matches[1]] = $matches[2]
        }
    }
    if (-not $credential.ContainsKey("username") -or -not $credential.ContainsKey("password")) {
        throw "没有找到可用的 GitHub 凭据。请先登录 GitHub 或配置 Personal Access Token。"
    }
    return $credential
}

function Invoke-GitHubApi {
    param(
        [string]$Method,
        [string]$Uri,
        [object]$Body = $null
    )

    $bytes = [System.Text.Encoding]::UTF8.GetBytes("$($script:Cred.username):$($script:Cred.password)")
    $basic = [Convert]::ToBase64String($bytes)
    $headers = @{
        Authorization = "Basic $basic"
        Accept = "application/vnd.github+json"
        "X-GitHub-Api-Version" = "2022-11-28"
        "User-Agent" = "desktop-pet-uploader"
    }

    if ($null -eq $Body) {
        return Invoke-RestMethod -Method $Method -Uri $Uri -Headers $headers
    }
    return Invoke-RestMethod -Method $Method -Uri $Uri -Headers $headers -ContentType "application/json" -Body ($Body | ConvertTo-Json -Depth 10)
}

$script:Cred = Get-GitHubCredential
$user = Invoke-GitHubApi -Method Get -Uri "https://api.github.com/user"
$owner = $user.login

$repo = $null
try {
    $repo = Invoke-GitHubApi -Method Get -Uri "https://api.github.com/repos/$owner/$RepoName"
    Write-Output "仓库已存在：$($repo.html_url)"
}
catch {
    $repo = Invoke-GitHubApi -Method Post -Uri "https://api.github.com/user/repos" -Body @{
        name = $RepoName
        description = $Description
        private = $false
        auto_init = $false
    }
    Write-Output "仓库已创建：$($repo.html_url)"
}

$remoteUrl = "https://github.com/$owner/$RepoName.git"
if (git remote get-url origin 2>$null) {
    git remote set-url origin $remoteUrl
}
else {
    git remote add origin $remoteUrl
}

git push -u origin master
Write-Output "上传完成：$($repo.html_url)"
