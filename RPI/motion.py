#!/usr/bin/env python3
# motion.py — WebSocket → Dual Teensy serial bridge (two motors on /dev/MOT1 and /dev/MOT2)
# deps: pip3 install websockets pyserial

import asyncio, json, signal, time
import serial, websockets

# ===== Config =====
TEENSY_PORT_1 = "/dev/MOT1"
TEENSY_PORT_2 = "/dev/MOT2"
BAUD          = 115200
TARGET_HZ     = 5750          # must match Teensy firmware cap
WS_HOST       = "0.0.0.0"
WS_PORT       = 8765

# ===== Serial Connections =====
print(f"[serial] opening {TEENSY_PORT_1} @ {BAUD}")
ser1 = serial.Serial(TEENSY_PORT_1, BAUD, timeout=0.2, write_timeout=0.2)
time.sleep(0.5)

print(f"[serial] opening {TEENSY_PORT_2} @ {BAUD}")
ser2 = serial.Serial(TEENSY_PORT_2, BAUD, timeout=0.2, write_timeout=0.2)
time.sleep(0.5)

# Clear buffers
ser1.reset_input_buffer()
ser2.reset_input_buffer()

def send_line(motor_num: int, line: str):
    """Send command to specified motor (1 or 2)"""
    try:
        ser = ser1 if motor_num == 1 else ser2
        ser.write((line.strip() + "\n").encode())
        ser.flush()
        resp = ser.readline().decode(errors="ignore").strip()
        if resp:
            print(f"[motor{motor_num}]", resp)
        return resp
    except Exception as e:
        print(f"[motor{motor_num} error]", e)
        return None

# ===== State (per motor) =====
state = {
    1: {"dir": None, "rate": 0.0, "hz": 0},  # Motor 1
    2: {"dir": None, "rate": 0.0, "hz": 0}   # Motor 2
}
_last_sent_dir = {1: None, 2: None}

# ===== Helpers =====
def compute_hz(rate01: float) -> int:
    try:
        r = float(rate01)
    except Exception:
        r = 0.0
    if r < 0: r = 0.0
    if r > 1: r = 1.0
    return int(round(r * TARGET_HZ))

def ensure_dir_sent(motor_num: int):
    """Send DIR:FWD/BWD if current state['dir'] hasn't been sent yet."""
    global _last_sent_dir
    d = state[motor_num]["dir"]
    if d is None:
        return False
    if d != _last_sent_dir[motor_num]:
        send_line(motor_num, "DIR:FWD" if d > 0 else "DIR:BWD")
        _last_sent_dir[motor_num] = d
    return True

def set_dir(motor_num: int, sign: int):
    """Set direction and, if rate>0, immediately (re)apply SPEED."""
    d = +1 if sign >= 0 else -1
    state[motor_num]["dir"] = d
    # 1) Make sure DIR is sent
    ensure_dir_sent(motor_num)
    # 2) If we have a stored rate > 0, resume motion even if rate hasn't changed
    if state[motor_num]["rate"] > 0:
        hz = compute_hz(state[motor_num]["rate"])
        state[motor_num]["hz"] = hz
        if hz > 0:
            send_line(motor_num, f"SPEED:{hz}")

def apply_rate(motor_num: int, rate01: float):
    """Set rate and push SPEED/STOP as needed; preserves rate across STOP."""
    try:
        r = float(rate01)
    except Exception:
        r = 0.0
    if r < 0: r = 0.0
    if r > 1: r = 1.0

    # Update stored rate (we keep it even if we stop)
    state[motor_num]["rate"] = r

    hz = compute_hz(r)

    # If rate is zero → STOP (and record that we are stopped)
    if hz <= 0:
        if state[motor_num]["hz"] != 0:
            state[motor_num]["hz"] = 0
            send_line(motor_num, "STOP")
        return

    # If rate > 0 but no direction set, wait until we get FWD/BWD
    if state[motor_num]["dir"] is None:
        print(f"[warn] motor{motor_num} rate>0 but no direction set, holding until FWD/BWD")
        state[motor_num]["hz"] = 0
        return

    # Ensure direction is communicated, then set SPEED
    ensure_dir_sent(motor_num)
    if hz != state[motor_num]["hz"]:
        state[motor_num]["hz"] = hz
        send_line(motor_num, f"SPEED:{hz}")

def stop_motor(motor_num: int):
    """Stop motor and clear direction"""
    if state[motor_num]["hz"] != 0:
        state[motor_num]["hz"] = 0
        send_line(motor_num, "STOP")
    state[motor_num]["dir"] = None

# ===== Motor Selection Helper =====
def get_motor_list(motor_spec):
    """Convert motor specification to list of motor numbers"""
    if motor_spec in ("both", "all"):
        return [1, 2]
    elif motor_spec in (1, 2, "1", "2"):
        return [int(motor_spec)]
    else:
        return []

# ===== WS handler =====
async def ws_handler(ws):
    print("[ws] client connected")
    try:
        async for msg in ws:
            # Accept JSON or plaintext
            payload = None
            motor_spec = None
            
            try:
                payload = json.loads(msg)
                motor_spec = payload.get("motor", 1)  # Default to motor 1 if not specified
            except Exception:
                # Plaintext commands default to motor 1
                m = msg.strip().lower()
                motor_spec = 1
                
                if   m == "fwd":  
                    set_dir(1, +1)
                    await ws.send('{"ok":true,"motor":1,"dir":"fwd"}')
                    continue
                elif m == "bwd":  
                    set_dir(1, -1)
                    await ws.send('{"ok":true,"motor":1,"dir":"bwd"}')
                    continue
                elif m == "stop":
                    stop_motor(1)
                    await ws.send('{"ok":true,"motor":1,"stop":true}')
                    continue
                else:
                    continue

            # Get list of motors to control
            motors = get_motor_list(motor_spec)
            if not motors:
                await ws.send(json.dumps({"ok": False, "err": f"invalid motor: {motor_spec}"}))
                continue

            cmd = (payload.get("cmd") or "").lower()

            # Execute command for each specified motor
            if cmd == "dir":
                val = (payload.get("value") or "").lower()
                if val == "fwd":
                    for m in motors:
                        set_dir(m, +1)
                    await ws.send(json.dumps({"ok": True, "motor": motor_spec, "dir": "fwd"}))
                elif val in ("bwd", "back", "backward"):
                    for m in motors:
                        set_dir(m, -1)
                    await ws.send(json.dumps({"ok": True, "motor": motor_spec, "dir": "bwd"}))

            elif cmd == "fwd":
                for m in motors:
                    set_dir(m, +1)
                await ws.send(json.dumps({"ok": True, "motor": motor_spec, "dir": "fwd"}))

            elif cmd == "bwd":
                for m in motors:
                    set_dir(m, -1)
                await ws.send(json.dumps({"ok": True, "motor": motor_spec, "dir": "bwd"}))

            elif cmd == "rate":
                rate_val = payload.get("value", 0.0)
                for m in motors:
                    apply_rate(m, rate_val)
                # Return status for all affected motors
                response = {"ok": True, "motor": motor_spec}
                for m in motors:
                    response[f"motor{m}"] = {
                        "hz": state[m]["hz"],
                        "rate": state[m]["rate"],
                        "dir": state[m]["dir"]
                    }
                await ws.send(json.dumps(response))

            elif cmd == "stop":
                for m in motors:
                    stop_motor(m)
                await ws.send(json.dumps({"ok": True, "motor": motor_spec, "stop": True}))

            elif cmd == "config":
                # CONFIG passthrough: send CONFIG:PARAM:VALUE to Teensy
                param = (payload.get("param") or "").upper()
                value = payload.get("value", 0)
                
                responses = []
                for m in motors:
                    resp = send_line(m, f"CONFIG:{param}:{value}")
                    responses.append(resp)
                
                await ws.send(json.dumps({
                    "ok": True,
                    "motor": motor_spec,
                    "config": param,
                    "value": value,
                    "responses": responses
                }))

            elif cmd == "status":
                response = {"ok": True}
                for m in motors:
                    response[f"motor{m}"] = {
                        "hz": state[m]["hz"],
                        "rate": state[m]["rate"],
                        "dir": state[m]["dir"]
                    }
                await ws.send(json.dumps(response))

            else:
                await ws.send(json.dumps({"ok": False, "err": f"unknown cmd {cmd}"}))
                
    except websockets.ConnectionClosed:
        print("[ws] client disconnected")

# ===== Main =====
async def main():
    async with websockets.serve(ws_handler, WS_HOST, WS_PORT, max_size=2**16):
        print(f"[ws] listening on ws://{WS_HOST}:{WS_PORT}")
        print(f"[serial] Motor 1: {TEENSY_PORT_1}")
        print(f"[serial] Motor 2: {TEENSY_PORT_2}")
        await asyncio.Future()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, loop.stop)
    try:
        loop.run_until_complete(main())
    finally:
        try: 
            ser1.close()
            ser2.close()
        except Exception: 
            pass