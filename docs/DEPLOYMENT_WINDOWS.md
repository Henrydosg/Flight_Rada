# Kế hoạch backup, triển khai và khôi phục — thao tác thủ công của người dùng

**Chưa có lệnh nào ở trang này được thực thi trên ESP32 trong phiên triển khai.** Không có upload, erase, mở serial monitor, ghi NVS hay filesystem lên thiết bị. Liệt kê lại cổng CH343 trước khi kết nối vì số COM có thể đổi.

Thư mục `build-baseline` đã được build lại sau tùy biến UI và là build cuối được kiểm chứng; baseline ban đầu được ghi riêng trong `validation/baseline.json`.

Flight Radar thay firmware Satellite Tracker. Hai app và hai filesystem không dùng chung layout. OTA cũ không phải đường rollback về Satellite Tracker. Chỉ thực hiện sau khi có full backup đã kiểm tra; Project A luôn giữ nguyên chỉ đọc.

## 1. Xác định thiết bị và chuẩn bị

Đóng serial monitor/PlatformIO monitor đang giữ cổng. Chạy PowerShell trong **Project B**:

```powershell
Get-PnpDevice -PresentOnly -Class Ports | Select-Object Status,FriendlyName
$port = Read-Host 'Nhap cong COM cua CH343 vua liet ke'
& ./tools/build_waveshare7.ps1 -BuildDirectory build-baseline
$idfPython = Join-Path $env:IDF_PYTHON_ENV_PATH 'Scripts/python.exe'
$idfPy = Join-Path $env:IDF_PATH 'tools/idf.py'
```

Helper build đã activate ESP-IDF 5.5.2 trong PowerShell hiện tại. Lệnh build không truy cập thiết bị.

## 2. Backup toàn bộ 8 MB trước khi ghi

Các lệnh esptool dưới đây do người dùng tự chạy. Kết nối ROM bootloader có thể reset/tạm dừng Satellite Tracker dù `read_flash` không ghi nội dung Flash:

```powershell
$backupDir = Join-Path (Get-Location) ('backup/satellite-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $backupDir | Out-Null
& $idfPython -m esptool --chip esp32s3 --port $port flash_id
& $idfPython -m esptool --chip esp32s3 --port $port get_security_info
& $idfPython -m esptool --chip esp32s3 --port $port --baud 115200 read_flash 0x0 0x800000 "$backupDir/full-8mb.bin"
if ($LASTEXITCODE -ne 0) { throw 'Backup failed; do not flash' }
if ((Get-Item "$backupDir/full-8mb.bin").Length -ne 0x800000) { throw 'Wrong backup length; do not flash' }
Get-FileHash "$backupDir/full-8mb.bin" -Algorithm SHA256 | Format-List | Out-File "$backupDir/SHA256.txt"
# Đọc lần hai để kiểm tra bản sao trùng nhau trước khi ghi firmware mới:
& $idfPython -m esptool --chip esp32s3 --port $port --baud 115200 read_flash 0x0 0x800000 "$backupDir/full-8mb-verify.bin"
if ($LASTEXITCODE -ne 0) { throw 'Second read failed; do not flash' }
if ((Get-FileHash "$backupDir/full-8mb.bin").Hash -ne (Get-FileHash "$backupDir/full-8mb-verify.bin").Hash) { throw 'Backup mismatch; do not flash' }
```

Giữ bản sao ở một nơi khác ngoài máy và ghi đường dẫn/sha256 trước khi tiếp tục. Full dump bao gồm bootloader, partition table, cả OTA slots, NVS, LittleFS và coredump. Nó không sao lưu eFuses. Nếu security info cho thấy Flash Encryption/Secure Boot đang bật, dừng kế hoạch raw restore này để xác định chính xác cơ chế khóa/chữ ký; không sửa eFuses và không erase để thử.

Việc đọc Flash có thể bị hạn chế bởi chế độ bảo mật/ROM. Không coi một file đủ byte là bản backup tốt nếu có lỗi esptool; cần hai lần đọc thành công và hash trùng.

## 3. Kiểm tra image offline rồi mới upload thủ công

```powershell
python tools/validate_firmware.py --build-dir build-baseline
& $idfPython -m esptool --chip esp32s3 image_info build-baseline/esp32flight.bin
& $idfPython -m esptool --chip esp32s3 image_info build-baseline/bootloader/bootloader.bin
```

Phải thấy PASS, ESP32-S3, header 8 MB ở cả bootloader và app. Cả app phải vừa hai slots 0x240000; tất cả payload kết thúc không quá 0x800000. Dừng nếu tool hoặc cấu hình báo 16 MB.

Sau khi người dùng tự quyết định thay Satellite Tracker:

```powershell
& $idfPython $idfPy -B build-baseline -p $port -b 230400 flash
```

Lệnh trên ghi **Flash của thiết bị** (gồm assets SPIFFS); không dùng web flasher upstream, `pio upload`, `uploadfs`, `erase_flash`, `erase_region`, factory reset hay thao tác NVS thủ công. Script helper của dự án không tự thực hiện lệnh này.

Layout local giữ NVS tại 0x9000 dài 0x5000 đúng Project A, không tăng page count lên 0x6000 như upstream. Khoảng 0xe000–0xefff được để trống; hai slots OTA và assets giữ nguyên offsets/kích thước upstream 8 MB. Không copy NVS từ layout khác. Không tự erase khi NVS init hoặc SPIFFS mount lỗi. NVS mới vẫn có thể ghi namespace Flight Radar/Wi-Fi trong vận hành sau triển khai; full backup là đường bảo toàn dữ liệu chính xác.

## 4. Thu serial log và xác nhận từng phần

```powershell
& $idfPython $idfPy -B build-baseline -p $port monitor 2>&1 | Tee-Object "$backupDir/flight-radar-runtime.log"
```

Monitor UART0 115200; thoát bằng Ctrl+]. Các mốc cần kiểm tra:

1. Boot header không báo “detected size 8192k smaller than image header”; target ESP32-S3; physical Flash 8,388,608; PSRAM 8,388,608. Không reset loop/watchdog/brownout.
2. Board log đúng LCD-7, 800×480, PCLK 14 MHz; H 4/43/8, V 4/12/8; framebuffer PSRAM/10-line bounce buffers. Không dùng board 7B/7C, không tự đổi timing nếu có vấn đề.
3. LCD hiển thị màu đúng, không lệch hàng/nhấp nháy sau Wi-Fi/TLS hoặc lưu settings. Xoay 180° như cấu hình A; kiểm tra bốn góc touch và nút Settings/5 tabs/zoom/tap aircraft.
4. Nhập Wi-Fi 2.4 GHz trong Settings. Kiểm tra observer 10.7769, 106.7009 mặc định hoặc sửa đúng vị trí thực; thời gian HCMC UTC+7. Không nhập key FlightAware để chạy radar cơ bản.
5. Quan sát dữ liệu adsb.lol/adsb.fi thật; so với nguồn dữ liệu cùng thời điểm. Callsign/type/altitude/speed/heading/distance; route chỉ có khi nguồn xác nhận. Không có aircraft phải thể hiện trạng thái rỗng rõ ràng.
6. Thử 5 views: detail/list, geographic route map, radar, statistics, retro. Touch mục tiêu nhỏ được thử trên board, không suy từ screenshot.
7. Ngắt/kết nối lại Wi-Fi, thử API lỗi/không có aircraft, đổi view lặp lại. Kiểm tra trạng thái stale/no data, phục hồi và không giữ mục tiêu cũ như live.
8. Chạy ít nhất 30–60 phút, theo dõi heap lớn nhất/free PSRAM/internal DMA, redraw/frame logs, touch, lỗi tile/PNG, task stack và reset reason. Đây là kiểm thử bắt buộc trước khi gọi firmware ổn định.

Nếu NVS/SPIFFS lỗi: giữ log, không format/erase. Nếu LCD có vấn đề: so với bảng `KNOWN_GOOD_HARDWARE.md` trước khi thay timing/GPIO/masks. Không tự chữa bằng tăng Flash 16 MB hoặc PSRAM 120 MHz.

## 5. Khôi phục Satellite Tracker từ full dump

Chỉ dùng backup từ **chính thiết bị này**, bảo mật đã được kiểm tra ở bước 2, hash còn đúng và file dài đúng 8 MB. Người dùng tự chạy:

```powershell
Get-FileHash "$backupDir/full-8mb.bin" -Algorithm SHA256
& $idfPython -m esptool --chip esp32s3 --port $port --baud 115200 write_flash --flash_mode keep --flash_freq keep --flash_size 8MB 0x0 "$backupDir/full-8mb.bin"
```

Đây là thao tác ghi toàn bộ vùng backup, khôi phục partition table/NVS/LittleFS/OTA cùng firmware A về đúng thời điểm backup. Không build, clean, sửa hay upload từ Project A. Sau restore, thu UART log và xác nhận Satellite Tracker, ISS 25544, bản đồ và touch trở lại. Chưa thực hiện kiểm chứng restore trên thiết bị trong phiên này.
