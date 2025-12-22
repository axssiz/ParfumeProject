# app.py
import asyncio, tempfile, os, json, subprocess
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

# serve frontend file
# helper: write bytes to temp webm file then convert to wav using ffmpeg
async def webm_to_wav(webm_path, wav_path):
    # requires ffmpeg installed on server
    cmd = ["ffmpeg", "-y", "-i", webm_path, "-ar", "16000", "-ac", "1", wav_path]
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    out, err = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {err.decode()}")
    return wav_path

# placeholder STT function
def stt_from_wav(wav_path):
    # TODO: call real STT (OpenAI Whisper API / Vosk / other)
    # For demo — return fake text
    return "Хочу сладкий стойкий аромат до двадцати тысяч"

# placeholder LLM call
def query_llm(prompt, session_id):
    # TODO: call OpenAI/other LLM here. Return a dict with 'answer' and optionally 'products'
    answer = "Рекомендую Montale Sweet Vanilla и Mancera Velvet Vanilla."
    products = [
        {"title":"Montale Sweet Vanilla","price":18000,"image":"/img/montale.jpg"},
        {"title":"Mancera Velvet Vanilla","price":20000,"image":"/img/mancera.jpg"}
    ]
    return {"answer": answer, "products": products}


app.mount("/", StaticFiles(directory=".", html=True), name="static")

@app.websocket("/ws/voice/{session_id}")
async def ws_voice(ws: WebSocket, session_id: str):
    await ws.accept()
    # create temp file to accumulate webm binary
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".webm")
    tmp_name = tmp.name
    print("Session", session_id, "tmp:", tmp_name)
    try:
        while True:
            msg = await ws.receive()
            if isinstance(msg, dict) and msg.get("type") == "websocket.receive":
                data = msg.get("bytes") or msg.get("text")
                # if it's JSON text event
                if isinstance(data, str):
                    try:
                        j = json.loads(data)
                        if j.get("event") == "eof":
                            # finish: close tmp file and process
                            tmp.close()
                            wav_path = tmp_name.replace(".webm", ".wav")
                            await webm_to_wav(tmp_name, wav_path)
                            text = stt_from_wav(wav_path)
                            # send interim transcript
                            await ws.send_text(json.dumps({"type":"transcript","payload":text}))
                            # query LLM
                            res = query_llm(text, session_id)
                            await ws.send_text(json.dumps({"type":"response","payload":res["answer"]}))
                            await ws.send_text(json.dumps({"type":"products","payload":res.get("products",[])}))
                            # cleanup
                            try:
                                os.remove(tmp_name)
                                os.remove(wav_path)
                            except Exception:
                                pass
                            # optionally keep websocket open for next utterance; continue loop
                        else:
                            # ignore other events
                            pass
                    except json.JSONDecodeError:
                        # binary frame sent as text? ignore
                        pass
                else:
                    # binary chunk (bytes)
                    bytes_data = data  # type: bytes
                    tmp.write(bytes_data)
            else:
                # websocket closed
                break
    except WebSocketDisconnect:
        print("Disconnected", session_id)
    except Exception as e:
        print("Error", e)
    finally:
        try:
            tmp.close()
        except:
            pass

# Rest API: receive text from browser STT fallback
@app.post("/api/voice/text")
async def voice_text(payload: dict):
    session = payload.get("sessionId")
    text = payload.get("text","")
    res = query_llm(text, session)
    return JSONResponse({"answer": res["answer"], "products": res.get("products",[])})

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
