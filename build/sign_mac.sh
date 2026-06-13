#!/bin/bash

# macOS アプリ署名・公証自動化スクリプト
#
# 事前準備:
# 1. Apple Developer Program に登録し、証明書「Developer ID Application」をキーチェーンにインストールしてください。
# 2. Apple ID の管理ページでアプリ専用パスワードを作成し、notarytool に登録してください：
#    xcrun notarytool store-credentials "Developer-ID" --apple-id "your-email@example.com" --team-id "YOUR_TEAM_ID"
# 3. 署名するアイデンティティ（Developer ID Application: Your Name (YOUR_TEAM_ID)）を確認してください：
#    security find-identity -v -p codesigning

set -e

# 設定項目（必要に応じて書き換えてください）
APP_NAME="ocr-automation"
APP_PATH="dist/${APP_NAME}.app"
ZIP_PATH="dist/${APP_NAME}-mac.zip"
DEVELOPER_ID="Developer ID Application: Your Name (YOUR_TEAM_ID)"  # キーチェーン内の証明書名
KEYCHAIN_PROFILE="Developer-ID"  # notarytool store-credentials で登録したプロファイル名

echo "=== 1. アプリのクリーンアップとビルド準備 ==="
if [ ! -d "$APP_PATH" ]; then
    echo "エラー: $APP_PATH が存在しません。先に PyInstaller ビルドを実行してください。"
    exit 1
fi

rm -f "$ZIP_PATH"

echo "=== 2. コード署名 (Codesign) ==="
# PyInstaller の bundle 内のすべての .dylib、.so、バイナリを再帰的に署名します。
# Hardened Runtime を有効にするために --options runtime を指定します。
echo "署名を実行中: $DEVELOPER_ID"
codesign --force --options runtime --deep --sign "$DEVELOPER_ID" "$APP_PATH"

echo "署名の検証中..."
codesign --verify --verbose --deep "$APP_PATH"
spctl --assess --verbose --type execute "$APP_PATH"

echo "=== 3. 公証 (Notarization) 用の ZIP 作成 ==="
echo "ZIPを圧縮中..."
ditto -c -k --keepParent "$APP_PATH" "$ZIP_PATH"

echo "=== 4. Apple 公証サービスへ送信 ==="
echo "公証をリクエスト中 (しばらく時間がかかります)..."
xcrun notarytool submit "$ZIP_PATH" --keychain-profile "$KEYCHAIN_PROFILE" --wait

echo "=== 5. 公証チケットのホチキス留め (Staple) ==="
echo "チケットをアプリに埋め込んでいます..."
xcrun stapler staple "$APP_PATH"

echo "公証結果の検証中..."
spctl --assess --verbose --type execute "$APP_PATH"

echo "=== 6. DMG インストーラの作成 (オプション) ==="
# create-dmg 等がインストールされている場合に実行可能
if command -v create-dmg &> /dev/null; then
    DMG_PATH="dist/${APP_NAME}-mac.dmg"
    rm -f "$DMG_PATH"
    echo "DMGインストーラを作成しています..."
    create-dmg \
        --volname "${APP_NAME} Installer" \
        --window-pos 200 120 \
        --window-size 600 400 \
        --icon-size 100 \
        --icon "${APP_NAME}.app" 175 120 \
        --hide-extension "${APP_NAME}.app" \
        --app-drop-link 425 120 \
        "$DMG_PATH" \
        "$APP_PATH"
    
    echo "DMGの署名中..."
    codesign --force --sign "$DEVELOPER_ID" "$DMG_PATH"
    
    echo "=== 完了 ==="
    echo "配布用 DMG ファイルが作成されました: $DMG_PATH"
else
    echo "=== 完了 ==="
    echo "アプリの署名・公証が完了しました。$ZIP_PATH を配布できます。"
fi
