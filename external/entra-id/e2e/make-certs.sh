#!/usr/bin/env bash
# E2E（mock モード）用の手元の認証局と、サーバー証明書を作る。
# 使い方: make-certs.sh <出力先ディレクトリ> [ホスト名 ...]
#   ホスト名の既定: localhost mock-entra mcp-server
# 出力: ca.crt / ca.key（手元の認証局）、<ホスト名>.crt / <ホスト名>.key（SAN に 127.0.0.1 も入れる）
# 作った鍵はテスト専用。リポジトリにはコミットしない。
set -euo pipefail
out="${1:?出力先ディレクトリを指定してください}"
shift || true
hosts=("$@")
[ ${#hosts[@]} -eq 0 ] && hosts=(localhost mock-entra mcp-server)
mkdir -p "$out"
cd "$out"
if [ ! -f ca.key ]; then
  openssl req -x509 -newkey rsa:2048 -nodes -days 825 -sha256 \
    -subj "/CN=graph-mcp-gateway E2E local CA" \
    -addext "basicConstraints=critical,CA:TRUE" -addext "keyUsage=critical,keyCertSign,cRLSign" \
    -addext "subjectKeyIdentifier=hash" \
    -keyout ca.key -out ca.crt 2>/dev/null
fi
for h in "${hosts[@]}"; do
  openssl req -newkey rsa:2048 -nodes -subj "/CN=$h" -keyout "$h.key" -out "$h.csr" 2>/dev/null
  # Python 3.13 以降の厳しい検証（VERIFY_X509_STRICT）に通るよう、鍵の識別子と鍵の用途を明示する
  printf 'subjectAltName=DNS:%s,DNS:localhost,IP:127.0.0.1\nextendedKeyUsage=serverAuth\nkeyUsage=critical,digitalSignature,keyEncipherment\nbasicConstraints=critical,CA:FALSE\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid,issuer\n' "$h" > "$h.ext"
  openssl x509 -req -in "$h.csr" -CA ca.crt -CAkey ca.key -CAcreateserial -days 825 -sha256 \
    -extfile "$h.ext" -out "$h.crt" 2>/dev/null
  rm -f "$h.csr" "$h.ext"
done
echo "作成しました: ${out}（ca.crt と ${hosts[*]} の証明書）"
