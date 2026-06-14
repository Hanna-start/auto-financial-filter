# -*- coding: utf-8 -*-
"""재무 스크리너 — 독립 창 런처.

streamlit 서버를 백그라운드(콘솔 없이)로 띄우고, pywebview 네이티브 창으로 연다.
창을 닫으면 서버도 함께 종료(orphan 방지). 브라우저 탭이 아니라 '자기 창'으로 떠서
작업표시줄 아이콘이 있는 진짜 데스크톱 프로그램처럼 동작한다.

실행: 재무스크리너.bat 더블클릭  (또는  pythonw launch.py)
"""
import os
import sys
import socket
import time
import subprocess
import atexit
from pathlib import Path
from urllib.request import urlopen

import webview

HERE = Path(__file__).resolve().parent


def free_port():
    """OS가 비어있는 포트를 골라주게 한다(고정 포트 충돌 회피)."""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def wait_ready(port, timeout=60):
    """streamlit 헬스 엔드포인트가 200을 줄 때까지 폴링."""
    url = f"http://127.0.0.1:{port}/_stcore/health"
    end = time.time() + timeout
    while time.time() < end:
        try:
            if urlopen(url, timeout=1).status == 200:
                return True
        except Exception:
            time.sleep(0.3)
    return False


def start_server(port):
    """streamlit을 헤드리스로 기동(브라우저 자동 오픈 끔, 콘솔 창 숨김)."""
    env = dict(os.environ, PYTHONUTF8="1")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    return subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(HERE / "app.py"),
         "--server.port", str(port),
         "--server.headless", "true",
         "--server.runOnSave", "false",
         "--browser.gatherUsageStats", "false"],
        cwd=str(HERE), env=env, creationflags=flags)


SPLASH = (
    "<body style='margin:0;height:100vh;display:flex;align-items:center;"
    "justify-content:center;background:#F9FAFB;"
    "font-family:Pretendard,-apple-system,\"Malgun Gothic\",sans-serif'>"
    "<div style='text-align:center'>"
    "<div style='font-size:44px'>📈</div>"
    "<div style='font-size:20px;font-weight:800;color:#191F28;margin-top:10px'>재무 스크리너</div>"
    "<div style='color:#8B95A1;font-size:14px;margin-top:8px'>불러오는 중…</div>"
    "</div></body>")


def main():
    port = free_port()
    proc = start_server(port)

    def cleanup():
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
    atexit.register(cleanup)

    # 창을 스플래시로 '즉시' 띄우고(체감 속도 ↑), 서버가 준비되면 앱 URL로 전환.
    window = webview.create_window("재무 스크리너", html=SPLASH,
                                   width=1300, height=880, min_size=(900, 600))

    def boot():
        # 한국 시세를 최근 거래일 EOD로 자동 갱신(거래일 인지 → 이미 최신이면 즉시 스킵).
        # 미국은 무거워 앱 안 '🔄 시세 새로고침' 버튼으로 수동. 갱신 실패는 앱 실행을 막지 않음.
        try:
            import refresh_prices
            for mk in ("KOSPI", "KOSDAQ"):
                refresh_prices.refresh_kr(mk)
        except Exception:
            pass
        if wait_ready(port):
            window.load_url(f"http://127.0.0.1:{port}")
        else:
            window.load_html(
                "<body style='font-family:sans-serif;padding:40px'>"
                "<h2>앱 시작 실패</h2><p>streamlit 서버가 뜨지 않았습니다. "
                "터미널에서 <code>streamlit run app.py</code>로 오류를 확인하세요.</p></body>")

    webview.start(boot)   # 창 표시 후 boot 실행, 창 닫힐 때까지 블록
    cleanup()             # 창 닫으면 서버 종료


if __name__ == "__main__":
    main()
