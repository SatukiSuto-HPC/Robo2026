@echo off
echo Interrupting running program on ESP32...
python -c "import serial, time; ser=serial.Serial('COM7', 115200, timeout=1); ser.write(b'\x03\x03\x03'); time.sleep(0.5); ser.close()"
ping 127.0.0.1 -n 2 > nul

echo Uploading config.py...
ampy -p COM7 -d 1 put config.py
ping 127.0.0.1 -n 2 > nul

echo Uploading boot.py...
ampy -p COM7 -d 1 put boot.py
ping 127.0.0.1 -n 2 > nul

echo Uploading line_follower.py...
ampy -p COM7 -d 1 put line_follower.py
ping 127.0.0.1 -n 2 > nul

echo Uploading uart_receiver.py...
ampy -p COM7 -d 1 put uart_receiver.py
ping 127.0.0.1 -n 2 > nul

echo Uploading task_mode.py...
ampy -p COM7 -d 1 put task_mode.py
ping 127.0.0.1 -n 2 > nul

echo Uploading a-mu.py...
ampy -p COM7 -d 1 put a-mu.py
ping 127.0.0.1 -n 2 > nul

echo Uploading a_mu.py...
ampy -p COM7 -d 1 put a_mu.py
ping 127.0.0.1 -n 2 > nul

echo Uploading web_server.py...
ampy -p COM7 -d 1 put web_server.py
ping 127.0.0.1 -n 2 > nul


echo Uploading index.html...
ampy -p COM7 -d 1 put index.html
ping 127.0.0.1 -n 2 > nul

echo Uploading main.py...
ampy -p COM7 -d 1 put main.py

echo Upload complete!
