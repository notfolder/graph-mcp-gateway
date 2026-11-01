#!/usr/bin/env bash
# E2E の実行スクリプト。
#   bash e2e/run.sh mock [--startup-only] [--skip-capacity]
#       mock モード（自動）。--startup-only は手順 3 の起動の確認で止める。--skip-capacity は処理量の測定を飛ばす（開発用）
#   bash e2e/run.sh real
#       real モード（配備済みの本システムに手元から接続する。.env の値を使う）
#   bash e2e/run.sh real-offsite [stop]
#       社外の確認用。mock の構成のうち言語モデルだけを .env の本物（Claude の API）に替えて起動する
# 1 つでも失敗があれば終了コード 1。ログは e2e/.work/logs/ に保存する。
set -uo pipefail
cd "$(dirname "$0")/.."

MODE="${1:-}"
shift || true
STARTUP_ONLY=0
SKIP_CAPACITY=0
OFFSITE_STOP=0
for arg in "$@"; do
  case "$arg" in
    --startup-only) STARTUP_ONLY=1 ;;
    --skip-capacity) SKIP_CAPACITY=1 ;;
    stop) OFFSITE_STOP=1 ;;
    *) echo "不明な引数: $arg" >&2; exit 2 ;;
  esac
done

WORK=e2e/.work
CERTS=$WORK/certs
LOGS=$WORK/logs
FAILED=0
BASE_FILES=(-f compose.yaml -f e2e/compose.mock.yaml)

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }
fail() { log "失敗: $*"; FAILED=1; }

EXTRA_PROFILES=()
dc() { docker compose --env-file "$ENV_FILE" "${BASE_FILES[@]}" ${EXTRA_FILES[@]+"${EXTRA_FILES[@]}"} --profile mock ${EXTRA_PROFILES[@]+"${EXTRA_PROFILES[@]}"} "$@"; }

# ---- 手順 1：作業場所と証明書 ---------------------------------------------------
prepare_work() {
  rm -rf "$WORK"
  mkdir -p "$CERTS/gateway" "$LOGS" "$WORK/devproxy-cert" "$WORK/llm" "$WORK/state" "$WORK/records"
  bash external/entra-id/e2e/make-certs.sh "$CERTS" mock-entra gateway >/dev/null
  cp "$CERTS/gateway.crt" "$CERTS/gateway/server.crt"
  cp "$CERTS/gateway.key" "$CERTS/gateway/server.key"
  openssl genrsa -out "$CERTS/mock-entra-signing.key" 2048 2>/dev/null
  # テスト専用の鍵。コンテナの root でない利用者が読めるようにする
  chmod 644 "$CERTS"/*.key "$CERTS/gateway/server.key"
  # まだ中身の無い束も、ディレクトリとしてマウントされないよう先にファイルを作る
  : > "$CERTS/devproxy-root.pem"
  : > "$CERTS/relay-bundle.pem"
  : > "$CERTS/owui-bundle.pem"
  : > "$CERTS/e2e-bundle.pem"
  chmod -R a+rwX "$WORK"
}

pem_join() { local f; for f in "$@"; do cat "$f"; echo; done; }

# ---- 手順 2：Dev Proxy のルート証明書と 3 つの束 ----------------------------------
make_bundles() {
  dc up -d devproxy >/dev/null 2>&1 || { fail "Dev Proxy を起動できません"; return 1; }
  local i
  for i in $(seq 1 60); do
    if dc run --rm --no-deps -T e2e python - >/dev/null 2>&1 <<'PY'
import os, urllib.request
req = urllib.request.Request("http://devproxy:8897/proxy/rootCertificate?format=crt",
                             headers={"Authorization": "Bearer " + os.environ["DEV_PROXY_API_TOKEN"]})
data = urllib.request.urlopen(req, timeout=5).read()
assert b"BEGIN CERTIFICATE" in data
open("/work/certs/devproxy-root.pem", "wb").write(data)
PY
    then break; fi
    sleep 2
  done
  grep -q "BEGIN CERTIFICATE" "$CERTS/devproxy-root.pem" || { fail "Dev Proxy のルート証明書を取り出せません"; return 1; }
  docker run --rm --entrypoint cat graph-mcp-gateway:test /etc/ssl/certs/ca-certificates.crt > "$CERTS/public-ca.pem"
  # 末尾に改行の無い PEM があるので、ファイルごとに改行を挟んでつなぐ
  pem_join "$CERTS/ca.crt" "$CERTS/devproxy-root.pem" "$CERTS/public-ca.pem" > "$CERTS/relay-bundle.pem"
  pem_join "$CERTS/ca.crt" "$CERTS/public-ca.pem" > "$CERTS/owui-bundle.pem"
  pem_join "$CERTS/ca.crt" "$CERTS/public-ca.pem" > "$CERTS/e2e-bundle.pem"
}

# ---- 起動の待ち合わせ ------------------------------------------------------------
wait_ready() {
  dc run --rm --no-deps -T e2e python e2e/support/wait_ready.py || { fail "起動の確認"; return 1; }
}

save_logs() {
  local phase="$1" svc idx count
  dc logs --no-color --timestamps > "$LOGS/$phase-compose.log" 2>&1
  for svc in ms365-full ms365-discovery; do
    count=$(dc ps -q "$svc" 2>/dev/null | wc -l | tr -d ' ')
    for idx in $(seq 1 "${count:-0}"); do
      mkdir -p "$LOGS/$phase-$svc-$idx"
      dc cp --index "$idx" "$svc:/tmp/ms365-logs/." "$LOGS/$phase-$svc-$idx/" >/dev/null 2>&1 || true
    done
  done
  log "ログを保存しました: $LOGS/$phase-*"
}

run_pytest() {
  local label="$1"; shift
  log "E2E: $label"
  dc run --rm --no-deps -T e2e pytest e2e -q -p no:cacheprovider -o addopts="" --ignore=e2e/host "$@" \
    2>&1 | tee "$LOGS/pytest-$label.log"
  local rc=${PIPESTATUS[0]}
  [ "$rc" -eq 0 ] || fail "E2E ${label}（終了コード ${rc}）"
}

host_pytest() {
  local label="$1"; shift
  log "E2E（ホスト）: $label"
  E2E_WORK_DIR="$WORK" E2E_CA_BUNDLE="$CERTS/e2e-bundle.pem" uv run --frozen pytest e2e/host -q -p no:cacheprovider \
    -o addopts="" "$@" 2>&1 | tee "$LOGS/pytest-$label.log"
  local rc=${PIPESTATUS[0]}
  [ "$rc" -eq 0 ] || fail "E2E ${label}（終了コード ${rc}）"
}

net_rx_bytes() {
  # 指定したサービスの各コンテナの受信バイト数（eth0）を「番号 バイト数」の行で出す
  local svc="$1" count idx
  count=$(dc ps -q "$svc" | wc -l | tr -d ' ')
  for idx in $(seq 1 "$count"); do
    printf '%s %s\n' "$idx" "$(dc exec -T --index "$idx" "$svc" cat /sys/class/net/eth0/statistics/rx_bytes 2>/dev/null | tr -d '\r')"
  done
}

mock_mode() {
  ENV_FILE=e2e/mock.env
  EXTRA_FILES=()
  log "手順 1：作業場所と証明書"
  docker compose --env-file "$ENV_FILE" "${BASE_FILES[@]}" --profile mock --profile multi --profile e2e down -v --remove-orphans >/dev/null 2>&1
  prepare_work
  log "イメージを作ります"
  docker build -q --target runtime -t graph-mcp-gateway:runtime . >/dev/null || { fail "runtime のビルド"; return; }
  docker build -q --target test -t graph-mcp-gateway:test . >/dev/null || { fail "test のビルド"; return; }

  log "手順 2：Dev Proxy のルート証明書と証明書の束"
  make_bundles || return

  log "手順 3：1 台構成を起動します（Open WebUI は最大 3 分）"
  dc up -d 2>&1 | tail -3
  wait_ready || { save_logs startup; return; }
  if [ "$STARTUP_ONLY" -eq 1 ]; then
    log "起動の確認まで通りました（--startup-only）。止めるには: docker compose --env-file e2e/mock.env -f compose.yaml -f e2e/compose.mock.yaml --profile mock down -v"
    return
  fi

  log "手順 4：基本のシナリオ"
  run_pytest phase4 -m "not phase5 and not restart_prepare and not restart_verify and not multi and not final"
  host_pytest host-phase4 -m "not multi"
  save_logs phase4

  log "手順 5：上限と直接出すツール、再起動後のサインインの維持"
  EXTRA_FILES=(-f e2e/compose.limits.yaml -f e2e/compose.eager.yaml)
  dc up -d --force-recreate --no-deps ms365-full ms365-discovery 2>&1 | tail -2
  wait_ready
  run_pytest phase5 -m "phase5"
  run_pytest restart-prepare -m "restart_prepare"
  dc up -d --force-recreate --no-deps relay-full relay-discovery 2>&1 | tail -2
  dc up -d --no-deps --force-recreate gateway 2>&1 | tail -1
  wait_ready
  run_pytest restart-verify -m "restart_verify"
  save_logs phase5

  if [ "$SKIP_CAPACITY" -eq 0 ]; then
    log "手順 6：1 台あたりの処理量の測定（約 15 分）"
    dc down >/dev/null 2>&1
    EXTRA_FILES=(-f e2e/compose.capacity.yaml)
    dc up -d 2>&1 | tail -2
    wait_ready
    dc run --rm --no-deps -T e2e python e2e/capacity/measure.py 2>&1 | tee "$LOGS/capacity.log"
    [ "${PIPESTATUS[0]}" -eq 0 ] || fail "処理量の測定"
    save_logs phase6
  else
    log "手順 6：処理量の測定を飛ばしました（--skip-capacity）"
  fi

  log "手順 7：台数を増やした構成"
  dc down >/dev/null 2>&1
  EXTRA_FILES=(-f e2e/compose.multi.yaml)
  EXTRA_PROFILES=(--profile multi)
  dc up -d 2>&1 | tail -2
  wait_ready
  net_rx_bytes ms365-full > "$WORK/state/rx-before-full.txt"
  net_rx_bytes ms365-discovery > "$WORK/state/rx-before-discovery.txt"
  run_pytest phase7 -m "multi"
  net_rx_bytes ms365-full > "$WORK/state/rx-after-full.txt"
  net_rx_bytes ms365-discovery > "$WORK/state/rx-after-discovery.txt"
  save_logs phase7
  host_pytest host-phase7 -m "multi"

  log "手順 8：単体・結合テスト（ネットワークなし）"
  docker compose --env-file "$ENV_FILE" --profile test run --rm unit 2>&1 | tee "$LOGS/unit.log"
  [ "${PIPESTATUS[0]}" -eq 0 ] || fail "単体・結合テスト"

  log "手順 9：トークンと個人のデータが外に出ないことの確認"
  run_pytest final -m "final"

  log "手順 10：停止とボリュームの削除"
  dc down -v --remove-orphans >/dev/null 2>&1
}

real_mode() {
  [ -f .env ] || { echo ".env がありません" >&2; exit 1; }
  set -a; . ./.env; set +a
  mkdir -p "$LOGS" "$WORK/state" "$WORK/records"
  log "real モード：配備済みの https://${PUBLIC_HOSTNAME}/ に手元から接続します"
  E2E_MODE=real E2E_BASE_HOST="${PUBLIC_HOSTNAME}" E2E_CA_BUNDLE="${E2E_CA_BUNDLE:-./certs/ca-bundle.pem}" \
    E2E_WORK_DIR="$WORK" uv run --frozen pytest e2e -q -p no:cacheprovider -o addopts="" --ignore=e2e/host \
    -m "not phase5 and not restart_prepare and not restart_verify and not multi and not final" \
    2>&1 | tee "$LOGS/pytest-real.log"
  [ "${PIPESTATUS[0]}" -eq 0 ] || fail "real モードの E2E"
  log "続けて e2e/real-checklist.md の手作業の手順を行ってください"
}

real_offsite_mode() {
  [ -f .env ] || { echo ".env がありません（OPENWEBUI_LLM_* を書いてください）" >&2; exit 1; }
  ENV_FILE=$WORK/offsite.env
  EXTRA_FILES=()
  if [ "$OFFSITE_STOP" -eq 1 ]; then
    dc down -v --remove-orphans
    return
  fi
  log "real-offsite：模擬の Entra ID・Graph と、.env の言語モデルで起動します"
  docker compose --env-file e2e/mock.env "${BASE_FILES[@]}" --profile mock down -v --remove-orphans >/dev/null 2>&1
  prepare_work
  # mock の値に、.env の言語モデルの 3 つだけを上書きする（鍵は画面にも記録にも出さない）
  cp e2e/mock.env "$ENV_FILE"
  grep -E '^OPENWEBUI_LLM_(BASE_URL|API_KEY|MODEL)=' .env >> "$ENV_FILE" || { echo ".env に OPENWEBUI_LLM_* がありません" >&2; exit 1; }
  # 手で確かめる間にトークンが切れないよう、模擬の Entra ID のトークンの期限を 1 時間にする
  echo "MOCK_ACCESS_TOKEN_LIFETIME=3600" >> "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  docker build -q --target runtime -t graph-mcp-gateway:runtime . >/dev/null
  docker build -q --target test -t graph-mcp-gateway:test . >/dev/null
  make_bundles || return
  dc up -d 2>&1 | tail -3
  wait_ready || return
  dc run --rm --no-deps -T e2e python e2e/support/offsite_setup.py 2>&1 | tee "$LOGS/offsite-setup.log"
  [ "${PIPESTATUS[0]}" -eq 0 ] || fail "Open WebUI の初期設定"
  log "起動しました。e2e/real-checklist.md の「社外の確認」の手順を行ってください。止めるには: bash e2e/run.sh real-offsite stop"
}

case "$MODE" in
  mock) mock_mode ;;
  real) real_mode ;;
  real-offsite) real_offsite_mode ;;
  *) echo "使い方: bash e2e/run.sh mock|real|real-offsite" >&2; exit 2 ;;
esac

if [ "$FAILED" -ne 0 ]; then
  log "失敗がありました（ログ: $LOGS/）"
  exit 1
fi
log "すべて通りました"
