"""Select isolated staging explicitly; production remains the default."""
import os
import subprocess
import sys

def isolated():
    selected=os.getenv("BXK_ISOLATED_STAGING","").strip().lower()=="true"
    if selected and (os.getenv("BXK_PREVIEW_MODE","").lower()!="true" or os.getenv("BXK_LIVE_TRADING_ENABLED","").lower()!="false"):
        raise RuntimeError("Isolated staging requires preview mode and live trading explicitly disabled")
    return selected

def main():
    app="staging_preview:app" if isolated() else "server:app"
    os.execv(sys.executable,[sys.executable,"-m","uvicorn",app,"--host","0.0.0.0","--port",os.getenv("PORT","8080")])

if __name__=="__main__":
    main()
