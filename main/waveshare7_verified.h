#pragma once

/* Hardware values read from Project A include/HB9IIUdisplayInit.h.
 * EXIO6 is named LCD_VDD in that known-good source. Its electrical function
 * is not inferred here; preserve exactly the proven output levels. */
#define W7_CH_MODE_ADDR       0x24
#define W7_CH_OUTPUT_ADDR     0x38
#define W7_CH_OUTPUT_MODE     0x01
#define W7_CH_TP_RESET        0x02
#define W7_CH_BACKLIGHT       0x04
#define W7_CH_LCD_VDD          0x40
#define W7_PCLK_HZ            14000000
#define W7_HSYNC_PULSE        4
#define W7_HSYNC_BACK_PORCH   43
#define W7_HSYNC_FRONT_PORCH  8
#define W7_VSYNC_PULSE        4
#define W7_VSYNC_BACK_PORCH   12
#define W7_VSYNC_FRONT_PORCH  8

static inline unsigned char w7_output_mask(int backlight, int touch_released)
{
    return W7_CH_LCD_VDD | (backlight ? W7_CH_BACKLIGHT : 0) |
           (touch_released ? W7_CH_TP_RESET : 0);
}
