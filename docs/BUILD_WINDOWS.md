# Build trên Windows — Waveshare LCD-7 / Flash 8 MB

Các lệnh ở trang này chỉ build và kiểm tra offline. Không dùng PlatformIO cho Flight Radar. Project A không phải thư mục build, assets hay toolchain.

## Môi trường dùng cho phiên triển khai

- ESP-IDF tag `v5.5.2`, commit `30aaf64524299d3bde422ca9a2848090d1bc5d0f`.
- Xtensa GCC `esp-14.2.0_20251107`, target ESP32-S3.
- Python 3.12.0 trong venv riêng của IDF; Python 3.13.5 + Pillow 12.3.0 cho assets/mockup.
- Node.js 22.17.1 có sẵn. Font C và sprite của tác giả đã commit nên không cần regenerate cho baseline.
- ImageMagick không có trong PATH; `tools/prepare_assets.py` dùng Pillow thay cho quantization/copy của shell script, tạo map từ Natural Earth thật.
- Host test: WinLibs GCC 14.2.0 POSIX portable. Không thay GCC, ESP-IDF hay Python hệ thống.
- ESP-IDF 6.0.2 có sẵn ở máy nhưng không được dùng cho firmware này; manifest chặn IDF >=6.

## Build lại bằng môi trường đã chuẩn bị

Build cuối đã được kiểm chứng ở `build-baseline` (dùng lại thư mục từ giai đoạn baseline; binary đã được build lại sau UI). Thêm `-BuildDirectory build-baseline` vào helper để tái sử dụng nó. Mặc định helper tạo build mới ở `build-waveshare7`; cả hai đều dùng cùng profile/gates.

Chạy PowerShell tại thư mục repo Flight_Rada.

```powershell
& ./tools/build_waveshare7.ps1 -BuildDirectory build-baseline
& ./tools/build_waveshare7.ps1 -BuildDirectory build-baseline -Action size
python tools/bootstrap_host_compiler.py
python tools/run_offline_tests.py
python tools/validate_firmware.py --build-dir build-baseline
```

Helper tự activate ESP-IDF trước khi gọi `idf.py`; action allow-list chỉ gồm build/reconfigure/size/size-components. Ccache bị tắt và cache tùy chọn được đưa về Project B. Không có flash/erase/monitor trong helper.

Profile được stack theo thứ tự: `sdkconfig.defaults` → `sdkconfig.board.8mb` → `sdkconfig.board.waveshare7-8mb`. CMake mặc định cũng chọn stack này. File `sdkconfig` cũ vẫn có thể lấn defaults, nên CMake kiểm tra cấu hình thực và dừng khi sai Flash/board/PSRAM/rotation/partition filename. Bộ kiểm tra sau link kiểm tra cả binary thực.

## Chuẩn bị lại trên máy khác

Đây là các lệnh tải công cụ vào **Project B**, không yêu cầu Administrator:

```powershell
git -c core.longpaths=true clone --branch v5.5.2 --depth 1 --recurse-submodules --shallow-submodules https://github.com/espressif/esp-idf.git .cache/esp-idf-v5.5.2
$env:IDF_TOOLS_PATH = Join-Path (Get-Location) '.cache/espressif'
# Chỉ đường dẫn Python 3.12 đã cài của bạn:
$bootstrapPython = 'C:/Path/To/Python312/python.exe'
& $bootstrapPython .cache/esp-idf-v5.5.2/tools/idf_tools.py --non-interactive install --targets esp32s3
& $bootstrapPython .cache/esp-idf-v5.5.2/tools/idf_tools.py --non-interactive install-python-env
python -m pip install Pillow==12.3.0
python tools/prepare_assets.py
& ./tools/build_waveshare7.ps1
```

Nếu Python bootstrap nằm chỗ khác, sửa biến đường dẫn; không sửa Project A. Cần mạng khi tải IDF/components/assets; build sau đó dùng cache. Asset preparation thất bại khi file bắt buộc tải lỗi hoặc PNG hỏng, không tạo asset giả để che lỗi.

## Kiểm thử UI thật bằng host

```powershell
python tools/bootstrap_host_compiler.py
python tools/build_simshot_windows.py
$env:PATH = "$(Get-Location)/.cache/host-compiler/mingw64/bin;$env:PATH"
Push-Location tools/simshot
& ../../build-host/simshot.exe --touch-smoke --stress 100 --views 0,1,2,3,4,s0,s1,s2 --snapshot ../../docs/validation/adsb-lol-hcmc.json --out ../../docs/ui/firmware-snapshot
& ../../build-host/simshot.exe --views 0,1,2,3,4 --out ../../docs/ui/firmware-empty
Pop-Location
```

Không có `--snapshot` thì renderer dùng zero aircraft. HTTP luôn trả lỗi trong harness, không gọi Internet, FlightAware, COM hay ESP32. `--snapshot` dùng phản hồi adsb.lol đã lưu, không phải live và không phát sinh máy bay giả. PPM là framebuffer RGB565 của LVGL được chuyển sang RGB24 để kiểm tra, không phải minh họa vẽ thay UI.

Nguồn chính thức: [ESP-IDF v5.5.2](https://github.com/espressif/esp-idf/tree/v5.5.2), [LVGL v8.4.0](https://github.com/lvgl/lvgl/tree/v8.4.0), [upstream esp32flight](https://github.com/theqkash/esp32flight). Kết quả build và test cụ thể được ghi trong báo cáo triển khai; hướng dẫn này không tự chứng minh PASS.

Đường lỗi HTTP đã kiểm tra bằng `simshot.exe --fetch-failure-smoke --snapshot ../../docs/validation/adsb-lol-hcmc.json --views 2 --out ../../docs/ui/firmware-fetch-failed` từ `tools/simshot`: worker fetch gốc chạy với HTTP stub lỗi, không có mạng thật. Settings trong host bật `APKFLIGHT_NO_WIFI`, nên các control Wi-Fi/password chỉ được build trong firmware, chưa kiểm tra runtime bằng host.

VS Code: task `Flight Radar: build IDF 5.5.2 (no flash)` trong `.vscode/tasks.json` gọi đúng helper với `build-baseline`; command của task đã được chạy để xác minh. File `.vscode/settings.json` xuất hiện trong phiên và đang chọn IDF 6.0.2 được giữ nguyên, không ghi đè cấu hình chưa commit. Dùng Run Build Task cho profile 5.5.2 này.

Renderer được chặn ghi/xóa/rename dưới `/assets` ở chế độ SIMSHOT. QA đã phát hiện và chuyển `days.tsv` do worker test tạo sang `build-host/test-sideeffects/`; gate manifest ngăn đóng gói runtime history hoặc cache vào assets chuẩn.
