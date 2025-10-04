# ASC Skid Steer Control System - Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## index.html

### [1.4.3] - 2025-10-04 - CRITICAL SAFETY FIX
#### Added
- **Emergency stop via B1 button** restored to gamepad loop
- B1 button (button index 0) now triggers immediate emergency stop

#### Fixed
- **CRITICAL**: Emergency stop was missing from gamepad polling loop in v1.4.2
- Robot could continue moving without ability to stop via gamepad
- Safety hazard where robot ran without operator control

#### Technical Details
- Added B1 button check at start of gamepad loop
- Calls `emergencyStop()` immediately when B1 pressed
- Sends stop command to both motors via WebSocket
- Visual feedback with flashing button animation

### [1.4.2] - 2025-10-04 - COMMAND THROTTLING & USER CONTROLS
#### Added
- Direction stability timer (prevents rapid direction flips)
- Rate change threshold (only sends if change ≥ threshold %)
- Configurable send rate slider in UI (50-500ms)
- Configurable rate threshold slider in UI (1-15%)
- Direction hold time input in UI (0-500ms)
- Filtered commands logging with reasons
- Live filtered command counter display

#### Problem Diagnosed
- 33.5 rate changes/sec and 3.8 direction changes/sec overwhelming motors
- Motor 2 reversed direction 3 times in 585ms during turning
- Small joystick corrections caused rapid direction flips
- Motors received conflicting commands mid-ramp

#### Solution
- **Direction Stability Timer**: Direction must be stable for `directionHoldMs` (default 200ms) before sending
- **Rate Change Threshold**: Only send rate updates if change exceeds `rateThresholdPct` (default 5%)
- **User-Adjustable Send Rate**: Slider to tune `sendRateMs` between 50-500ms

#### Impact
- Intelligent command filtering reduces unnecessary updates by 70-90%
- Direction changes reduced from 3.8/sec to <1/sec
- Rate changes reduced from 33.5/sec to ~3-5/sec
- Motors only receive commands when meaningful changes occur

#### Technical Details
- Added `directionIsStable()` function to track direction hold time
- Added `rateChangeExceedsThreshold()` function for threshold checking
- State tracking: `lastSentDir`, `lastSentRate`, `dirChangeTime`, `pendingDir`
- Filtered commands logged with type: "direction_not_stable" or "rate_change_below_threshold"
- All throttling parameters persist in localStorage

### [1.4.1] - 2025-10-04 - CRITICAL BUG FIX
#### Changed
- **sendRateMs: 50ms → 100ms** (command rate reduced from 20Hz to 10Hz)

#### Problem Diagnosed
- Serial buffer overflow at 115200 baud causing motor instability
- Commands sent in bursts of 4 (dir+rate for both motors) within 2ms
- Each command takes 2-3ms to transmit, but new commands sent before previous complete
- Peak rate: ~80 commands/second, but serial can only handle ~40 commands/second
- Symptoms: Motor jamming, whining, "remembered commands" (delayed execution)

#### Log Analysis Results
- 654 commands sent in 87 seconds = 7.5 avg/second
- Commands arrive in rapid bursts causing queue buildup
- Response delays: 5-20ms (normal 1-2ms), indicating buffer saturation
- 100% response rate (no lost commands), but execution delayed

#### Impact
- Halves command rate: 80/sec → 40/sec (within serial bandwidth)
- Reduces burst pressure on serial buffers
- Eliminated "remembered commands" issue
- Updates still smooth at 10Hz (human perception limit ~15Hz)

#### Migration
- Auto-updates old configs from 50ms to 100ms on first load
- Existing users see console message about the change

### [1.4.0] - 2025-10-04 - LOGGING SYSTEM
#### Added
- Comprehensive logging system for debugging motor control issues
- Downloadable JSON log files with timestamped entries
- Live log display showing last 50 entries
- Log entry types: gamepad, command, response, error, system
- Session management with unique session IDs
- Log statistics display (entry count, duration)

#### Features
- Start/stop logging buttons
- Download log as JSON with timestamp in filename
- Clear log button
- Auto-scroll log display
- Color-coded log entries by type
- Session summary on stop (entry counts by type, duration, filtered commands)

#### Technical Details
- Captures: gamepad axes, commands sent, responses received, timing data
- Timestamp: milliseconds since session start
- Log format: `{session_id, start_time, duration_ms, config, entries[]}`
- Entry format: `{timestamp, type, data}`

### [1.3.0] - 2025-10-04 - EMERGENCY STOP
#### Added
- Emergency stop functionality with joystick override protection
- B1 button triggers emergency stop
- Reactivation pattern: short press + 2-second hold of B1
- Visual feedback with flashing red button animation

#### Features
- Immediate stop command to both motors on B1 press
- Emergency state prevents accidental reactivation
- Two-step reactivation pattern for safety
- Console logging of e-stop events
- 2-second timeout between pattern steps

#### Technical Details
- E-stop state machine: normal → stopped → reactivating → normal
- Pattern timing: <500ms press, then hold >2000ms within window
- Button animation: `@keyframes flash` for visual indication
- WebSocket command: `{motor: "both", cmd: "stop"}`

### [1.2.0] - 2025-10-04 - THROTTLE DISPLAY
#### Added
- Throttle Hz display showing Axis 3 output as frequency limit
- Real-time Hz calculation based on throttle position

#### Features
- Display format: "Throttle Hz: 5750"
- Calculation: `throttleHz = Math.round(CONFIG.control.hzCap * baseRate)`
- Updates in real-time with gamepad axis 3

#### Technical Details
- baseRate conversion: Axis 3 (+1 → 0%, 0 → 50%, -1 → 100%)
- Hz range: 0 to CONFIG.control.hzCap (default 5750)
- Display element: `<span id="throttleHz">0</span>`

### [1.1.0] - 2025-10-04 - INDEPENDENT DEADZONES
#### Added
- Independent deadzone sliders for Axis 1 (Y) and Axis 2 (Twist)
- Real-time value display for each deadzone setting
- Automatic migration from old single deadzone to separate deadzones

#### Changed
- Config structure: replaced single `deadzone` with `deadzoneY` and `deadzoneTwist`
- `processAxis()` function now accepts deadzone as a parameter for per-axis control
- UI layout: deadzones now on separate row for better organization

#### Technical Details
- Both deadzones range from 0.00 to 0.20 with 0.01 step precision
- Default values: deadzoneY=0.05, deadzoneTwist=0.05
- Backward compatibility: old configs with single deadzone auto-migrate on load
- Each axis can now be tuned independently to eliminate drift

### [1.0.0] - 2025-10-03 - INITIAL RELEASE
#### Added
- Differential steering control (Y-axis + Twist blending)
- Gamepad input with configurable axes
- Real-time track status visualization
- Teensy configuration panel (HOLD, RAMP, FSTART, FEEDINT, MAXHZ)
- Control parameters (Hz cap, sensitivity γ, deadzone)
- WebSocket connection to RPi bridge at ws://192.168.1.43:8765
- localStorage persistence for all settings
- Emergency stop button (UI only)
- Sync config to both Teensys
- Mode indicators (STOPPED, FORWARD, BACKWARD, ROTATE, TURNS)
- Left/Right track status displays
- Auto-scaling to prevent speed overshoots
- Sensitivity curve (power function) for fine control

#### Technical Details
- Differential steering: `left = fwd + rot`, `right = fwd - rot`
- Auto-normalization when combined speed exceeds ±1.0
- Deadzone compensation with scaling
- Rate conversion: 0.0-1.0 → 0-5750 Hz
- Default send rate: 50ms (20 Hz)
- Config stored in `localStorage.ascSkidSteerConfig`

---

## main.cpp (Teensy Firmware)

### [1.0.0] - 2025-10-03 - INITIAL RELEASE
#### Added
- IntervalTimer-based step pulse generation
- Hardware limit: TARGET_FREQ_MAX = 5750 Hz (immutable)
- Configurable parameters via CONFIG: commands
- S-curve (cosine) acceleration/deceleration ramping
- Safe direction change state machine (decel → hold → flip → accel)
- Serial command interface: DIR:FWD/BWD, SPEED:<hz>, STOP, CONFIG:PARAM:VALUE
- Periodic feedback: FB DIR:<dir> FREQ:<hz>

#### Configurable Parameters
- HOLD (0-1000ms): Pause time during direction changes
- RAMP (50-5000ms): Acceleration/deceleration time
- FSTART (50-500Hz): Starting frequency for ramps
- FEEDINT (100-10000ms): Feedback message interval
- MAXHZ (100-5750Hz): Software frequency limit

#### Technical Details
- Timer resolution: microseconds
- Step pulse width: 5µs
- Ramp calculation: Cosine S-curve for smooth motion
- State machine: IDLE, ACCEL, DECEL, RUN, HOLD, FLIP
- Serial baud rate: 115200
- Feedback format: `FB DIR:FWD FREQ:2500`

---

## motion.py (Python WebSocket Bridge)

### [1.1.0] - 2025-10-04 - CONFIG COMMAND SUPPORT
#### Added
- CONFIG command passthrough to Teensy microcontrollers
- Response collection from both motors
- Multi-line response handling for config updates

#### Features
- Send config to individual motor or both simultaneously
- Collect and return all config responses
- Format: `{"motor": "both", "cmd": "config", "value": {HOLD: 100, RAMP: 1000, ...}}`

#### Technical Details
- Converts JSON config object to CONFIG:PARAM:VALUE serial commands
- Waits for responses with 200ms timeout
- Returns array of responses: `["MOT1: CONFIG HOLD=100", "MOT2: CONFIG HOLD=100", ...]`

### [1.0.0] - 2025-10-03 - INITIAL RELEASE
#### Added
- WebSocket server on 0.0.0.0:8765
- Dual serial bridge to /dev/MOT1 and /dev/MOT2 at 115200 baud
- Motor selection: individual (1, 2) or both ("both", "all")
- Command handlers: dir, fwd, bwd, rate, stop, status
- Per-motor state tracking (direction, rate, Hz)
- JSON and plaintext command parsing
- Rate normalization from 0.0-1.0 to 0-5750 Hz
- Direction state management with persistence
- Automatic serial buffer clearing on startup

#### Technical Details
- **Serial Ports**: /dev/MOT1, /dev/MOT2
- **Baud Rate**: 115200
- **Timeout**: 200ms read/write
- **Target Hz**: 5750 (must match Teensy firmware)
- **Dependencies**: websockets, pyserial

#### Command Format
- JSON: `{"motor": 1|2|"both", "cmd": "dir|rate|stop|config", "value": ...}`
- Plaintext: `fwd`, `bwd`, `stop` (defaults to motor 1)

---

## System Integration

### Hardware Requirements
- 2x Teensy 3.x or 4.x microcontrollers
- 2x Stepper motor drivers (STEP/DIR interface)
- Raspberry Pi or similar for WebSocket bridge
- USB gamepad/joystick with twist axis

### Software Requirements
- **Browser**: Modern browser with Gamepad API support
- **Python**: 3.7+ with websockets and pyserial
- **Arduino IDE**: 1.8+ or PlatformIO for Teensy compilation

### Communication Flow
```
Gamepad → Browser UI → WebSocket → Python Bridge → Serial → Teensy 1 & 2 → Motor Drivers
```

### Configuration Synchronization
All runtime parameters can be updated from browser UI and are synced to both Teensys simultaneously.

---

## Version Numbering

**MAJOR.MINOR.PATCH**
- **MAJOR**: Breaking changes to command protocol or hardware interface
- **MINOR**: New features, backward-compatible additions
- **PATCH**: Bug fixes, optimizations, documentation updates

---

## License

**Proprietary** - All rights reserved. This software and associated documentation are proprietary and confidential.

## Contributors

**Grant du Toit** - Owner/Founder  
**Daniel Ikekwem** - Lead Developer

## Contact

For questions, issues, or contributions regarding the ASC Skid Steer Control System, please contact the project maintainer.

---

**Last Updated**: 2025-10-04  
**Document Version**: 1.4.3