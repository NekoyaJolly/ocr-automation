# Windows アプリコード署名自動化 PowerShell スクリプト
#
# 事前準備:
# 1. Windows SDK がインストールされており、signtool.exe が PATH に通っているか、
#    または標準インストールパス（"C:\Program Files (x86)\Windows Kits\..."）にあることを確認してください。
# 2. 有効なコード署名証明書（PFXファイルなど）を準備してください。

$ErrorActionPreference = "Stop"

# 設定項目
$AppName = "ocr-automation"
$TargetExe = "dist\ocr-automation\ocr-automation.exe"
$CertPath = "path\to\your\certificate.pfx"  # 証明書ファイルのパス
$CertPassword = "your-password"             # 証明書のパスワード（またはパスワードプロンプトを使用）
$TimestampUrl = "http://timestamp.digicert.com" # タイムスタンプサーバーURL

# 1. 署名対象の存在確認
if (-not (Test-Path $TargetExe)) {
    Write-Error "エラー: $TargetExe が見つかりません。先に PyInstaller ビルドを実行してください。"
}

# 2. signtool.exe の検索（PATH にない場合のフォールバック）
$SignTool = "signtool.exe"
if (-not (Get-Command $SignTool -ErrorAction SilentlyContinue)) {
    # Windows Kits フォルダから最新の signtool.exe を探す
    $SdkPaths = Get-ChildItem "C:\Program Files (x86)\Windows Kits\10\bin\*\x64\signtool.exe" -ErrorAction SilentlyContinue
    if ($SdkPaths) {
        $SignTool = $SdkPaths[0].FullName
    } else {
        Write-Warning "signtool.exe が見つかりませんでした。PATH に通っている必要があります。"
    }
}

Write-Host "=== 1. アプリケーション本体の署名 ==="
Write-Host "実行中: $SignTool sign /f $CertPath ..."

# 署名の実行
& $SignTool sign /f $CertPath /p $CertPassword /t $TimestampUrl /d "OCR Automation" /du "https://github.com/jolly-app/ocr-automation-v1" $TargetExe

Write-Host "=== 2. 署名の検証 ==="
& $SignTool verify /pa $TargetExe

Write-Host "=== 3. インストーラ（Inno Setup 等で作成した場合）の署名（オプション） ==="
$InstallerPath = "dist\ocr-automation-setup.exe"
if (Test-Path $InstallerPath) {
    Write-Host "インストーラを署名しています..."
    & $SignTool sign /f $CertPath /p $CertPassword /t $TimestampUrl /d "OCR Automation Setup" $InstallerPath
    & $SignTool verify /pa $InstallerPath
}

Write-Host "=== 完了 ==="
Write-Host "コード署名が正常に完了しました。"
