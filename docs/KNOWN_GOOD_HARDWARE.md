# Known-Good Hardware Configuration

Project A là mã Satellite Tracker do chủ dự án cung cấp để đối chiếu tại chỗ. Các đường dẫn và số dòng trong bảng thuộc bản tham chiếu đó.
Project B: repository hiện tại, upstream commit `b62a100a4ec967b296a0426ac895b3e7aa5ffd31`.

Quy ước bằng chứng: **HW** = người dùng xác nhận runtime trong yêu cầu; **SRC** = đọc được trong source/artifact, chưa đo độc lập trên phần cứng trong phiên này; **?** = chưa xác định. Không có thao tác serial hoặc ghi Flash nào trong quá trình triển khai.

| Component | Satellite Tracker và nguồn cụ thể trong A | Flight Radar trước sửa | Cấu hình triển khai / Result |
|---|---|---|---|
| Flash vật lý | **8 MB HW**, `platformio.ini:29`–`34`; `.pio/build/DISPLAY/firmware.bin` byte 3 high nibble = 3 (8 MB), image 1,715,712 bytes **SRC** | `sdkconfig.defaults:7` khai báo 16 MB | Profile riêng 8 MB, gate CMake + kiểm tra header app/bootloader và binary partitions |
| Flash mode / speed | QIO, `platformio.ini:25`–`26`; framework Arduino `tools/sdk/esp32s3/qio_opi/include/sdkconfig.h:34`–`39`: QIO boot / header DIO, 80 MHz **SRC** | QIO 80 MHz | Giữ QIO 80 MHz. Header DIO do bootloader đổi sang QIO là hợp lệ; không ép header QIO |
| PSRAM | 8 MB OPI **HW**; `platformio.ini:25`–`28`; framework header `sdkconfig.h:307,312`: OCT / 80 MHz **SRC** | OPI 80 MHz, XIP code/rodata | OPI 80 MHz; giữ PSRAM XIP cho bounce buffers. Log runtime capacity + heap |
| RGB GPIO D0…D15 | `14,38,18,17,10,39,0,45,48,47,21,1,2,42,41,40`, `include/HB9IIUdisplayInit.h:128`–`144` **HW/SRC** | Trùng mapping | Giữ nguyên mapping |
| Sync GPIO | DE 5, VSYNC 3, HSYNC 46, PCLK 7, `include/HB9IIUdisplayInit.h:145`–`149` **HW/SRC** | Trùng | Giữ nguyên |
| RGB pixel clock | 14,000,000 Hz, `include/HB9IIUdisplayInit.h:150` **SRC**; màn hình này đã chạy **HW** | 16 MHz | 14 MHz trong `main/waveshare7_verified.h` |
| HSYNC | pulse 4, back porch 43, front porch 8, polarity 0, `include/HB9IIUdisplayInit.h:152`–`155` **SRC** | 4 / 8 / 8 | Khớp 4 / 43 / 8 |
| VSYNC | pulse 4, back porch 12, front porch 8, polarity 0, `include/HB9IIUdisplayInit.h:156`–`159` **SRC** | 4 / 8 / 8 | Khớp 4 / 12 / 8 |
| Pixel polarity | negative active PCLK; DE idle low; PCLK idle low, `include/HB9IIUdisplayInit.h:160`–`162` **SRC** | negative PCLK, zero-initialized other flags | Khớp |
| Resolution | 800×480 RGB565, `include/HB9IIUdisplayInit.h:128,169`–`172` **HW/SRC** | 800×480 | Giữ nguyên; không dùng 7B 1024×600 |
| LCD enable/reset | Source đặt tên EXIO6 `CH_LCD_VDD=0x40`, `include/HB9IIUdisplayInit.h:74`–`76,93`–`101`. Không reset LCD qua GPIO riêng; chức năng điện chính xác của EXIO6 chưa đo **?** | Generic masks bật EXIO3/4/5, không giữ EXIO6 | Giữ đúng các mức đã dùng thành công; không suy đoán EXIO3 hay chức năng điện EXIO6 |
| CH422G | WR_SET `0x24`, giá trị `0x01`; WR_IO `0x38`, `include/HB9IIUdisplayInit.h:67`–`90` **SRC** | Đúng địa chỉ, khác masks | Dùng cùng địa chỉ. Reset/backlight-off `0x40 → 0x42`, on `0x46`, off `0x42` |
| Backlight | EXIO2 `0x04`; EXIO1 release `0x02`; EXIO6 giữ `0x40`, `include/HB9IIUdisplayInit.h:74`–`76,104`–`112` **HW/SRC** | on `0x1e`, off `0x1a` | Đổi chỉ cho profile verified. Không PWM CH422G; giữ I²C owner duy nhất |
| I²C / GT911 | I²C0 SDA8 SCL9, 400 kHz, address `0x5d`, INT4; reset qua CH422G, `include/HB9IIUdisplayInit.h:184`–`192` **HW/SRC** | Cùng bus; thử 0x5d/0x14 | Giữ fallback 0x14 của tác giả, address thực tế cần log runtime |
| Touch coordinates | x 0…799, y 0…479; offset_rotation 0, `include/HB9IIUdisplayInit.h:180`–`187`; toàn display `setRotation(2)` tại dòng 243 **HW/SRC** | Rotation 0 | LVGL rotation 180 và touch mirror cả hai trục; cần kiểm tra bốn góc trên thiết bị |
| Touch reset timing | `include/HB9IIUdisplayInit.h:216`–`228`: reset low 10 ms rồi release 50 ms **SRC** | Generic sequence 100/100/200 ms với masks khác | Giữ trình tự low/release A, backlight tắt đến frame đầu |
| Framebuffer | RGB PSRAM allocation `lib/LovyanGFX/src/lgfx/v1/platforms/esp32s3/Bus_RGB.cpp:238`–`251`; LVGL 800×480×2=768,000 bytes PSRAM `src/lv_driver.h:33,128`–`136` **SRC** | ESP-IDF double framebuffer/direct mode | Giữ driver ESP-IDF; rotation 180 dùng ba framebuffer (2,304,000 bytes). Không copy Arduino driver |
| DMA | DMA descriptor allocation internal DMA-capable, chunks 4,032 bytes, `lib/LovyanGFX/src/lgfx/v1/platforms/esp32s3/Bus_RGB.cpp:253`–`278`; burst 64B tại dòng 233 **SRC** | PSRAM alignment 64; bounce 10 lines | Giữ IDF bounce 8,000 pixels ×2 buffers×2B =32,000B internal; đây là lựa chọn IDF, chưa xác nhận HW |
| USB/UART | CDC-on-boot `platformio.ini:50`; dual Serial0/Serial 115200, `include/HB9IIUdisplayInit.h:25`–`48` **SRC**; USB-to-UART CH343 được nhận diện trong Windows **HW** | IDF default console | UART0 115200 chính; USB Serial/JTAG phụ. Không đồng nhất USB Serial/JTAG với Arduino USB CDC. COM hiện tại chưa kiểm tra bằng mở cổng |
| Diagnostics | Capacity/largest heap DMA và PSRAM tại `include/HB9IIUdisplayInit.h:51`–`57`; no USB-host wait tại dòng 25–35 **SRC** | Một số log boot/reset | Thêm capacity guard và buffer budgets; không erase NVS khi mount/init lỗi |

## Các bản sửa cần bảo toàn

- Commit A `f0885e3` sửa Flash 8 MB, RGB color/byte order, kiểm tra cấp phát framebuffer/DMA, map/PNG và LVGL dirty rectangle. Chỉ đọc lịch sử; không chuyển các truy cập thanh ghi LovyanGFX sang ESP-IDF.
- `src/lv_driver.h:26`–`27,69`–`93,145`: flush các vùng invalidated, VSYNC một lần mỗi refresh, `full_refresh=0`.
- `src/main.cpp:78` mount LittleFS với `formatOnFail=false`; giữ dữ liệu khi lỗi filesystem. Project B dùng SPIFFS assets riêng, khác layout A.

Nguồn ESP-IDF cho lựa chọn framebuffer/bounce/XIP: [RGB LCD v5.5.2](https://docs.espressif.com/projects/esp-idf/en/v5.5.2/esp32s3/api-reference/peripherals/lcd/rgb_lcd.html). Đây là hướng dẫn driver; không phải bằng chứng runtime cho board của người dùng.
