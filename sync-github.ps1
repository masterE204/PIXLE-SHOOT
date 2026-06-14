cd "C:\Users\ETHAN\pixle shoot"
git add -A
$msg = "Auto-sync: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
    git commit -m $msg
    git push origin main
    Write-Host "Pushed: $msg"
} else {
    Write-Host "Nothing to sync."
}
