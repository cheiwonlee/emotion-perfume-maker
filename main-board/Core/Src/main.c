/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Daily Mood Perfume Maker - Combined Controller
  * @note           : Uses Job Queue & State Machine for LoRa (Matches Syringe Code)
  ******************************************************************************
  */
  /* USER CODE END Header */
  /* Includes ------------------------------------------------------------------*/
#include "main.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include <stdio.h>
#include <string.h>
#include "sx1272/radio.h"
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */
typedef enum {
    SCREEN_START = 0,
    SCREEN_MOOD_SELECT,
    SCREEN_CONFIRM,
    SCREEN_BLENDING,
    SCREEN_FINISH
} UI_State_t;

// [추가] 상태 머신 열거형
typedef enum {
    LOWPOWER = 0,
    IDLE,
    RX,
    RX_TIMEOUT,
    RX_ERROR,
    TX,
    TX_TIMEOUT
} States_t;

// [추가] 주사기 모터와 통신할 구조체 (순서 중요)
typedef struct {
    int sensor_id;
    float rotation_ml;
} StepingMotor_t;
/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */
#define TOUCH_KEY0   (1U << 0)
#define TOUCH_KEY1   (1U << 1)
#define TOUCH_KEY2   (1U << 2)
#define TOUCH_KEY3   (1U << 3)
#define TOUCH_KEY4   (1U << 4)
#define TOUCH_KEY5   (1U << 5)
#define TOUCH_KEY6   (1U << 6)
#define TOUCH_KEY7   (1U << 7)

// --- LoRa 설정 ---
#define RF_FREQUENCY                                922100000
#define TX_OUTPUT_POWER                             14
#define LORA_BANDWIDTH                              0
#define LORA_SPREADING_FACTOR                       7
#define LORA_CODINGRATE                             1
#define LORA_PREAMBLE_LENGTH                        8
#define LORA_SYMBOL_TIMEOUT                         0
#define LORA_FIX_LENGTH_PAYLOAD_ON                  false
#define LORA_IQ_INVERSION_ON                        false
#define RX_TIMEOUT_VALUE                            1000
#define BUFFER_SIZE                                 64

// --- ID 설정 ---
#define PACKET_ID   121

#define MY_ID       PACKET_ID
#define SYRINGE_ID  PACKET_ID
#define Rx_ID       PACKET_ID

// --- 모터 핀 ---
#define IN1_PORT GPIOA
#define IN1_PIN  GPIO_PIN_9
#define IN2_PORT GPIOB
#define IN2_PIN  GPIO_PIN_10
#define IN3_PORT GPIOB
#define IN3_PIN  GPIO_PIN_4
#define IN4_PORT GPIOB
#define IN4_PIN  GPIO_PIN_5

// --- 센서 핀 ---
#define LIMIT_SWITCH_PORT GPIOA
#define LIMIT_SWITCH_PIN  GPIO_PIN_12
#define PROX_SENSOR_PORT  GPIOA
#define PROX_SENSOR_PIN   GPIO_PIN_15

#define ONE_CYCLE 4096

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */
/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/
SPI_HandleTypeDef hspi1;
TIM_HandleTypeDef htim2;
UART_HandleTypeDef huart2;
UART_HandleTypeDef huart3;

/* USER CODE BEGIN PV */
// UI
volatile UI_State_t currentState = SCREEN_START;
volatile uint8_t needsRedraw = 1;
volatile uint8_t selectedMood = 0;

// Touch
volatile uint8_t lastEventState = 1;
volatile uint32_t lastTouchTime = 0;
volatile uint8_t lora_ok_flag = 0; // check OK message
volatile uint8_t lora_wait_flag = 0; // check wait

const char* moodNames[] = {
    "NULL", "Fresh", "Calm", "Bold", "Sweet",
    "Active", "Cozy", "Mystic", "Random"
};

uint8_t touchData = 0;

// [추가] LoRa 상태 머신 변수
States_t State = IDLE;
uint16_t BufferSize = BUFFER_SIZE;
uint8_t Buffer[BUFFER_SIZE];
int8_t RssiValue = 0;
int8_t SnrValue = 0;

// [추가] Job Queue (전송할 작업 목록)
#define JOB_QUEUE_SIZE 10
StepingMotor_t g_jobQueue[JOB_QUEUE_SIZE];
int g_jobTotal = 0;
int g_jobIndex = 0;

// Motor
int current_angle = 0;
int Lavender_angle = 0;
int Cedarwood_angle = 90;
int Vanilla_angle = 180;
int Bergamot_angle = 270;
int move_angle = 0;
int value = 0;
const int Bottle_Angles[] = { 0, 45, 135, 225, 315 };
volatile uint8_t isSyringeDone = 0;

const uint8_t half_step_sequence[8][4] = {
    {1, 0, 0, 0}, {1, 1, 0, 0}, {0, 1, 0, 0}, {0, 1, 1, 0},
    {0, 0, 1, 0}, {0, 0, 1, 1}, {0, 0, 0, 1}, {1, 0, 0, 1}
};

static RadioEvents_t RadioEvents;
/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_USART3_UART_Init(void);
static void MX_SPI1_Init(void);
static void MX_TIM2_Init(void);
static void MX_USART2_UART_Init(void);

/* USER CODE BEGIN PFP */
// LCD
void FlushUARTBuffer(void);
void LCD_Clear(void);
void LCD_EnableTouchKeys(void);
uint8_t LCD_SendTouchRequest(void);
void LCD_DrawString(uint8_t x, uint8_t y, const char* str, uint8_t size);

// UI
void Draw_Screen_Start(void);
void Draw_Screen_MoodSelect(void);
void Draw_Screen_Confirm(uint8_t mood);
void Draw_Screen_Blending(void);
void Draw_Screen_Finish(void);
void ProcessTouch(uint8_t touchData);
void Draw_Screen_Message(const char* line1, const char* line2);

// Motor & Logic
void SetMotorPins(uint8_t a, uint8_t b, uint8_t c, uint8_t d);
void MoveMotorSteps(int steps, int delay_ms);
void ResetMotor(void);
void MoveToAngle(int target_angle);
void step_steps(int motor_id, int steps, int delay_ms); // Dummy wrapper

void RunBlendingProcess(uint8_t mood);
void SendSyringeCommand(float amount);
void WaitForSyringe(void);

// LoRa Helper
uint16_t PrepareTxPacket(int sensor_id, float rotation_ml);
void SendStartCommand(uint8_t mood);   // ★ 추가: Start 패킷 전송 함수 프로토타입

// Callbacks
void OnTxDone(void);
void OnRxDone(uint8_t* payload, uint16_t size, int16_t rssi, int8_t snr);
void OnTxTimeout(void);
void OnRxTimeout(void);
void OnRxError(void);
/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */
extern UART_HandleTypeDef huart2;
int _write(int file, char* ptr, int len) {
    HAL_UART_Transmit(&huart2, (uint8_t*)ptr, len, 100);
    return len;
}
// [수정] 서브보드 응답 기다리기
//  예전 WaitForLoRaOK_Blocking() 은 DONE 이 올 때까지 끝없이 기다렸다.
//  이제 "LOW"(향료 부족) 응답과 시간 초과도 처리해서, 서브보드가 멈춰도 메인보드가 같이 멈추지 않는다.
typedef enum {
    REPLY_DONE = 0,   // 주입 완료
    REPLY_LOW,        // 향료 부족으로 서브보드가 작업을 거절
    REPLY_TIMEOUT     // 정해진 시간 안에 응답 없음
} SyringeReply_t;

#define LEVEL_LOW     0
#define LEVEL_OK      1
#define LEVEL_UNKNOWN 0xFF

uint8_t g_reply_level = LEVEL_UNKNOWN;  // DONE 응답에 실려 온 주입 후 수위

SyringeReply_t WaitForSyringeReply(uint32_t timeout_ms)
{
    uint32_t start = HAL_GetTick();
    lora_ok_flag = 0;
    lora_wait_flag = 1;
    printf("Waiting for reply (Rx_ID = %d)...\n", Rx_ID);

    while (HAL_GetTick() - start < timeout_ms)
    {
        State = IDLE;
        Radio.Rx(RX_TIMEOUT_VALUE);
        while (State != RX && State != RX_TIMEOUT && State != RX_ERROR) {
            HAL_Delay(10);
        }
        if (State != RX) continue;  // 타임아웃/에러 → 다시 수신
        State = IDLE;

        if (Buffer[0] != Rx_ID) {
            printf("Received message with wrong Rx_ID: %d\n", Buffer[0]);
            continue;
        }
        if (BufferSize >= 5 && strncmp((char*)&Buffer[1], "DONE", 4) == 0) {
            g_reply_level = (BufferSize >= 6) ? Buffer[5] : LEVEL_UNKNOWN;
            lora_wait_flag = 0;
            printf("Received DONE message!\n");
            return REPLY_DONE;
        }
        if (BufferSize >= 5 && strncmp((char*)&Buffer[1], "LOW", 3) == 0) {
            lora_wait_flag = 0;
            printf("Received LOW message (sensor %d)\n", Buffer[4]);
            return REPLY_LOW;
        }
        printf("Received message, but not DONE/LOW\n");
    }
    lora_wait_flag = 0;
    printf("No reply within %lu ms\n", (unsigned long)timeout_ms);
    return REPLY_TIMEOUT;
}

// [추가] 송신이 끝날 때까지 기다림 (Radio.Send 는 바로 반환되므로, 곧바로 Radio.Rx 를 부르면
//  아직 나가는 중인 패킷이 끊길 수 있음). OnTxDone/OnTxTimeout 이 State 를 IDLE 로 바꾼다.
void WaitTxDone(void)
{
    uint32_t tx_start = HAL_GetTick();
    while (State == TX && HAL_GetTick() - tx_start < 3500) {
        HAL_Delay(1);
    }
}

// [추가] 향료 통 4개의 수위를 서브보드에 물어보고 대시보드용으로 출력
//  요청: [ID]"LVL?"   응답: [ID]"LVL"[통1][통2][통3][통4]  (값: 1 충분 / 0 부족 / 0xFF 센서 없음)
//  부팅 직후, 시작 화면에 들어올 때, 시작 화면에서 30초마다 호출 → 통을 다시 채운 것도 대시보드에 반영됨
uint32_t lastLevelQuery = 0;
#define LEVEL_QUERY_INTERVAL_MS 30000

void QueryLevels(void)
{
    lastLevelQuery = HAL_GetTick();
    Buffer[0] = PACKET_ID;
    memcpy(Buffer + 1, "LVL?", 4);
    State = TX;
    Radio.Send(Buffer, 5);
    WaitTxDone();

    uint32_t start = HAL_GetTick();
    while (HAL_GetTick() - start < 2000)
    {
        State = IDLE;
        Radio.Rx(RX_TIMEOUT_VALUE);
        while (State != RX && State != RX_TIMEOUT && State != RX_ERROR) {
            HAL_Delay(10);
        }
        if (State != RX) continue;
        State = IDLE;
        if (Buffer[0] == Rx_ID && BufferSize >= 8 && strncmp((char*)&Buffer[1], "LVL", 3) == 0)
        {
            for (int sensor_id = 1; sensor_id <= 4; sensor_id++) {
                uint8_t level = Buffer[3 + sensor_id];
                if (level == LEVEL_LOW)     printf("WATER_X : %d\n", sensor_id);  // [대시보드]
                else if (level == LEVEL_OK) printf("WATER_O : %d\n", sensor_id);  // [대시보드]
            }
            return;
        }
    }
    printf("No level reply from syringe board\n");
}

// --- [추가] 패킷 생성 함수 (주사기 모터 코드와 호환) ---
uint16_t PrepareTxPacket(int sensor_id, float rotation_ml)
{
    StepingMotor_t Steping_to_send;
    Steping_to_send.sensor_id = sensor_id;
    Steping_to_send.rotation_ml = rotation_ml;

    // 첫 바이트에 ID(PACKET_ID = 121) 넣음
    Buffer[0] = SYRINGE_ID;
    memcpy(Buffer + 1, &Steping_to_send, sizeof(StepingMotor_t));

    return (1 + sizeof(StepingMotor_t));
}

// ★ Start 버튼을 눌렀을 때 주사기에게 "시작" 신호 보내는 함수
void SendStartCommand(uint8_t mood)
{
    // ID
    Buffer[0] = PACKET_ID;

    // "START" + mood
    Buffer[1] = 'S';
    Buffer[2] = 'T';
    Buffer[3] = 'A';
    Buffer[4] = 'R';
    Buffer[5] = 'T';
    Buffer[6] = mood;    // 선택된 무드 번호

    uint16_t size = 7;

    printf("LoRa: SEND START (mood=%d)\n", mood);
    Radio.Send(Buffer, size);
}

// --- Motor Control ---
void SetMotorPins(uint8_t a, uint8_t b, uint8_t c, uint8_t d) {
    HAL_GPIO_WritePin(IN1_PORT, IN1_PIN, (GPIO_PinState)a);
    HAL_GPIO_WritePin(IN2_PORT, IN2_PIN, (GPIO_PinState)b);
    HAL_GPIO_WritePin(IN3_PORT, IN3_PIN, (GPIO_PinState)c);
    HAL_GPIO_WritePin(IN4_PORT, IN4_PIN, (GPIO_PinState)d);
}

void MoveMotorSteps(int steps, int delay_ms) {
    int direction = (steps > 0) ? 1 : -1;
    steps = (steps > 0) ? steps : -steps;
    static int current_step_index = 0;
    for (int i = 0; i < steps; i++) {
        current_step_index = (current_step_index + direction + 8) % 8;
        SetMotorPins(
            half_step_sequence[current_step_index][0],
            half_step_sequence[current_step_index][1],
            half_step_sequence[current_step_index][2],
            half_step_sequence[current_step_index][3]
        );
        HAL_Delay(delay_ms);
    }
}

// [수정] 향료 하나 주입 — 예전 LavenderMove / CedarwoodMove / VanillaMove / BergamotMove 4개를 하나로 합침
//  1) 회전판을 해당 향료 위치로 돌리고  2) 서브보드에 주입 요청  3) 응답을 기다린다
const char* perfumeNames[] = { "NULL", "Lavender", "Cedarwood", "Vanilla", "Bergamot" };
const int perfumeAngles[] = { 0, 0, 90, 180, 270 };  // Lavender_angle, Cedarwood_angle, Vanilla_angle, Bergamot_angle

SyringeReply_t InjectPerfume(int sensor_id, float ml)
{
    move_angle = perfumeAngles[sensor_id] - current_angle;
    if (move_angle > 180) move_angle -= 360;
    if (move_angle < -180) move_angle += 360;
    MoveMotorSteps(1024 * move_angle / 90, 2);
    current_angle = (current_angle + move_angle + 360) % 360;

    printf("PERFUME : %s : %d\n", perfumeNames[sensor_id], (int)ml); // [대시보드] 주입량 (newlib-nano 기본 설정은 %f 를 출력하지 않아 정수로)
    uint16_t packetSize = PrepareTxPacket(sensor_id, ml);
    printf("sensor_id: %d, rotation_ml: %d\n", sensor_id, (int)ml);
    State = TX;
    Radio.Send(Buffer, packetSize);
    WaitTxDone();  // 송신이 끝난 뒤 수신으로 전환

    // 서브보드는 1ml 에 4096 스텝, 스텝당 1ms 이상 → 넉넉하게 2배 + 10초
    uint32_t timeout_ms = (uint32_t)(ml * ONE_CYCLE * 2) + 10000;
    SyringeReply_t reply = WaitForSyringeReply(timeout_ms);

    // [대시보드] 향료 통 수위 (센서가 없는 통은 출력하지 않음)
    if (reply == REPLY_LOW || (reply == REPLY_DONE && g_reply_level == LEVEL_LOW)) {
        printf("WATER_X : %d\n", sensor_id);
    } else if (reply == REPLY_DONE && g_reply_level == LEVEL_OK) {
        printf("WATER_O : %d\n", sensor_id);
    }
    return reply;
}

// Dummy wrapper for compatibility with snippet
void step_steps(int motor_id, int steps, int delay_ms) {
    // 여기서는 단순히 딜레이 용도로 사용 (실제 모터는 MoveMotorSteps가 함)
    (void)motor_id;
    (void)steps;
    HAL_Delay(delay_ms);
}

void ResetMotor(void) {
    printf("[Motor] Resetting to Home...\n");
    /* UI + LoRa 테스트 때문에 주석 처리함
    while(HAL_GPIO_ReadPin(LIMIT_SWITCH_PORT, LIMIT_SWITCH_PIN) == GPIO_PIN_SET) {
       MoveMotorSteps(-1, 2);
    }
    */
    current_angle = 0;
    printf("[Motor] Homed.\n");
}

void MoveToAngle(int target_angle) {
    move_angle = target_angle - current_angle;
    if (move_angle > 180) move_angle -= 360;
    if (move_angle < -180) move_angle += 360;
    int steps = (int)(4096.0 * (float)move_angle / 360.0);
    printf("[Motor] Moving to %d deg (%d steps)\n", target_angle, steps);
    MoveMotorSteps(steps, 2);
    current_angle = target_angle;
}

// 기분별 레시피 (Lavender, Cedarwood, Vanilla, Bergamot) — 단위 ml
//  dashboard/sensor/constants.py 의 RECIPES 와 같아야 한다.
const float RECIPES[8][4] = {
    { 0, 0, 0, 0 },   // 0: 없음
    { 1, 1, 1, 4 },   // 1: fresh
    { 8, 4, 2, 2 },   // 2: calm
    { 2, 6, 2, 4 },   // 3: confident
    { 4, 2, 8, 2 },   // 4: sweet & romantic
    { 2, 2, 2, 10 },  // 5: energetic
    { 4, 4, 8, 2 },   // 6: cozy
    { 1, 4, 1, 1 },   // 7: deep & mystic
};

// --- Blending Logic: 선택된 mood에 따라 로터리 모터 + 주사기 동작 ---
void RunBlendingProcess(uint8_t mood)
{
    printf(">>> Blending Start: Mood %d <<<\n", mood);

    if (mood < 1 || mood > 7) {
        printf("[Blending] Unknown mood: %d\n", mood);
        currentState = SCREEN_MOOD_SELECT;
        needsRedraw = 1;
        return;
    }

    for (int sensor_id = 1; sensor_id <= 4; sensor_id++)
    {
        SyringeReply_t reply = InjectPerfume(sensor_id, RECIPES[mood][sensor_id - 1]);
        if (reply != REPLY_DONE)
        {
            // [추가] 향료 부족 / 서브보드 무응답이면 제조를 멈추고 기분 선택 화면으로 돌아간다
            if (reply == REPLY_LOW) {
                printf("[Blending] %s is LOW - stopped\n", perfumeNames[sensor_id]);
                Draw_Screen_Message("Refill needed:", perfumeNames[sensor_id]);
            } else {
                printf("[Blending] No reply from syringe board - stopped\n");
                Draw_Screen_Message("No reply from", "syringe board");
            }
            HAL_Delay(2500);
            ResetMotor();
            currentState = SCREEN_MOOD_SELECT;
            needsRedraw = 1;
            return;
        }
    }

    printf(">>> Blending Complete! <<<\n");
    ResetMotor();                 // 블렌딩 끝난 후 홈으로
    currentState = SCREEN_FINISH; // Finish 화면으로 전환
    needsRedraw = 1;
}

// --- LCD Functions ---
void FlushUARTBuffer(void) {
    uint8_t dummy;
    int count = 0;
    while (__HAL_UART_GET_FLAG(&huart3, UART_FLAG_RXNE)) {
        HAL_UART_Receive(&huart3, &dummy, 1, 1);
        count++; if (count > 50) break;
    }
    HAL_Delay(2);
    while (__HAL_UART_GET_FLAG(&huart3, UART_FLAG_RXNE)) {
        HAL_UART_Receive(&huart3, &dummy, 1, 1);
    }
}
void LCD_EnableTouchKeys(void) {
    FlushUARTBuffer();
    uint8_t cmd[] = { 0x02, 0x35, 0x49, 0x3F, 0x3F, 0x03, 0x00 };
    uint8_t sum = 0;
    for (int i = 1; i <= 5; i++) sum += cmd[i];
    cmd[6] = sum;
    HAL_UART_Transmit(&huart3, cmd, sizeof(cmd), HAL_MAX_DELAY);
    HAL_Delay(200);
}
void LCD_Clear(void) {
    uint8_t cmd[] = { 0x02, 0x34, 0x42, 0x33, 0x03, 0x00 };
    uint8_t sum = 0;
    for (int i = 1; i <= 4; i++) sum += cmd[i];
    cmd[5] = sum;
    HAL_UART_Transmit(&huart3, cmd, sizeof(cmd), HAL_MAX_DELAY);
    HAL_Delay(500);
}
void LCD_DrawString(uint8_t x, uint8_t y, const char* str, uint8_t size) {
    uint8_t str_len = strlen(str);
    if (str_len > 16) str_len = 16;
    uint8_t data_n = 4 + str_len;
    uint8_t packet_len = 2 + data_n + 2;
    uint8_t cmd[32] = { 0 };
    cmd[0] = 0x02; cmd[1] = 0x30 + 2 + data_n; cmd[2] = 0x42;
    cmd[3] = (size == 2) ? 0x32 : 0x31; cmd[4] = 0x30 + x; cmd[5] = 0x30 + y;
    memcpy(&cmd[6], str, str_len); cmd[6 + str_len] = 0x03;
    uint8_t sum = 0;
    for (int i = 1; i < packet_len - 1; i++) sum += cmd[i];
    cmd[packet_len - 1] = sum;
    HAL_UART_Transmit(&huart3, cmd, packet_len, HAL_MAX_DELAY);
    HAL_Delay(100);
}
uint8_t LCD_SendTouchRequest(void) {
    FlushUARTBuffer();
    uint8_t tx[5] = { 0x02, 0x33, 0x45, 0x03, 0x7B };
    HAL_UART_Transmit(&huart3, tx, sizeof(tx), 100);
    uint8_t allData[50];
    int totalCount = 0;
    uint32_t startTime = HAL_GetTick();
    while ((HAL_GetTick() - startTime) < 200 && totalCount < 50) {
        if (__HAL_UART_GET_FLAG(&huart3, UART_FLAG_RXNE)) {
            HAL_UART_Receive(&huart3, &allData[totalCount], 1, 1);
            totalCount++;
        }
    }
    if (totalCount == 0) return 0;
    for (int i = 0; i <= totalCount - 7; i++) {
        if (allData[i] != 0x02) continue;
        if (allData[i + 2] != 0x45) continue;
        if (allData[i + 5] != 0x03) continue;
        uint8_t bcc_calc = 0;
        for (int k = 1; k <= 5; k++) bcc_calc += allData[i + k];
        if (bcc_calc != allData[i + 6]) continue;
        uint8_t d1 = allData[i + 3];
        uint8_t d2 = allData[i + 4];
        return ((d1 & 0x0F) << 4) | (d2 & 0x0F);
    }
    return 0;
}
static uint8_t DecodeMoodFromTouch(uint8_t touchData) {
    if (touchData & (1 << 7)) return 1;
    if (touchData & (1 << 3)) return 2;
    if (touchData & (1 << 6)) return 3;
    if (touchData & (1 << 2)) return 4;
    if (touchData & (1 << 5)) return 5;
    if (touchData & (1 << 1)) return 6;
    if (touchData & (1 << 4)) return 7;
    if (touchData & (1 << 0)) return 8;
    return 0;
}

// --- UI ---
void Draw_Screen_Start(void) {
    printf("STATUS : SCREEN_START\n");      // [대시보드] 화면 상태
    LCD_Clear(); HAL_Delay(50);
    LCD_DrawString(25, 30, "DAILY MOOD", 1); HAL_Delay(50);
    LCD_DrawString(13, 48, "PERFUME MAKER", 1); HAL_Delay(50);
    LCD_DrawString(5, 104, "Tap to continue", 1);
}
void Draw_Screen_MoodSelect(void) {
    printf("STATUS : SCREEN_MOODSELECT\n"); // [대시보드] 화면 상태
    LCD_Clear();
    LCD_DrawString(6, 6, "Fresh", 1); LCD_DrawString(74, 6, "Calm", 1); HAL_Delay(50);
    LCD_DrawString(6, 40, "Bold", 1); LCD_DrawString(74, 40, "Sweet", 1); HAL_Delay(50);
    LCD_DrawString(6, 74, "Active", 1); LCD_DrawString(74, 74, "Cozy", 1); HAL_Delay(50);
    LCD_DrawString(6, 108, "Mystic", 1); LCD_DrawString(74, 108, "Random", 1);
}
void Draw_Screen_Confirm(uint8_t mood) {
    printf("STATUS : SCREEN_CONFIRM\n");    // [대시보드] 화면 상태
    LCD_Clear();
    char moodTitle[24];
    sprintf(moodTitle, "Mood: %s", moodNames[mood]);
    LCD_DrawString(20, 40, moodTitle, 1); HAL_Delay(50);
    LCD_DrawString(7, 106, "[Back]", 1);
    LCD_DrawString(70, 106, "[Start]", 1);
}
void Draw_Screen_Blending(void) {
    printf("STATUS : SCREEN_BLENDING\n");   // [대시보드] 화면 상태
    LCD_Clear();
    LCD_DrawString(20, 50, "Blending...", 1); HAL_Delay(100);
    LCD_DrawString(20, 70, "Please wait!", 1);
}
void Draw_Screen_Finish(void) {
    printf("STATUS : SCREEN_FINISH\n");     // [대시보드] 화면 상태
    LCD_Clear();
    LCD_DrawString(40, 15, "Finish!", 1); HAL_Delay(100);
    LCD_DrawString(16, 40, "Your perfume", 1); HAL_Delay(50);
    LCD_DrawString(15, 60, "is now ready.", 1); HAL_Delay(50);
    LCD_DrawString(22, 104, "Tap to home", 1);
}

// [추가] 두 줄짜리 안내 화면 (향료 부족, 통신 오류 등)
void Draw_Screen_Message(const char* line1, const char* line2) {
    LCD_Clear();
    LCD_DrawString(10, 40, line1, 1); HAL_Delay(50);
    LCD_DrawString(10, 60, line2, 1);
}

void ProcessTouch(uint8_t touchData) {
    HAL_GPIO_WritePin(GPIOA, GPIO_PIN_5, GPIO_PIN_SET);
    HAL_Delay(20);
    printf("ProcessTouch: 0x%02X (state=%d)\n", touchData, currentState);

    switch (currentState) {
    case SCREEN_START:
        currentState = SCREEN_MOOD_SELECT; needsRedraw = 1;
        break;
    case SCREEN_MOOD_SELECT: {
        uint8_t keyMask = touchData;
        if (keyMask == 0) {
            for (int retry = 0; retry < 3; ++retry) {
                HAL_Delay(30);
                uint8_t extra = LCD_SendTouchRequest();
                if (extra != 0) { keyMask = extra; break; }
            }
        }
        uint8_t mood = DecodeMoodFromTouch(keyMask);
        if (mood == 8) {
            uint32_t tick = HAL_GetTick();
            mood = (tick % 7) + 1;
        }
        if (mood == 0) break;
        selectedMood = mood;
        printf("MOOD : %d\n", mood);           // [대시보드] 선택한 기분 (Random 은 실제로 정해진 번호)
        currentState = SCREEN_CONFIRM; needsRedraw = 1;
        break;
    }
    case SCREEN_CONFIRM: {
        if (touchData & TOUCH_KEY4) {
            // [Back]
            currentState = SCREEN_MOOD_SELECT; needsRedraw = 1;
        }
        else if (touchData & TOUCH_KEY0) {
            // [Start] 눌렀을 때 LoRa로 START + mood 전송
            lora_ok_flag = 0;                  // DONE 플래그 초기화
            SendStartCommand(selectedMood);    // START 패킷 전송

            currentState = SCREEN_BLENDING;    // Blending 화면으로 전환
            needsRedraw = 1;
        }
        break;
    }
    case SCREEN_BLENDING:
        // Blending 중에는 터치 무시
        break;
    case SCREEN_FINISH:
        currentState = SCREEN_START; selectedMood = 0; needsRedraw = 1;
        break;
    }
    HAL_GPIO_WritePin(GPIOA, GPIO_PIN_5, GPIO_PIN_RESET);
    if (needsRedraw) HAL_Delay(300);
}
/* USER CODE END 0 */

int main(void) {
    HAL_Init();
    SystemClock_Config();
    MX_GPIO_Init();
    MX_USART3_UART_Init();
    MX_SPI1_Init();
    MX_TIM2_Init();
    MX_USART2_UART_Init();

    printf("Combined UI & Motor Controller (Queue Ver)\n");
    HAL_Delay(2500);

    // ResetMotor(); // 하드웨어 연결 후 주석 해제

    uint8_t pb7_init = HAL_GPIO_ReadPin(GPIOB, GPIO_PIN_7);
    lastEventState = pb7_init;
    lastTouchTime = HAL_GetTick();

    LCD_Clear(); HAL_Delay(100); LCD_Clear();
    LCD_EnableTouchKeys();

    RadioEvents.TxDone = OnTxDone;
    RadioEvents.RxDone = OnRxDone;
    RadioEvents.TxTimeout = OnTxTimeout;
    RadioEvents.RxTimeout = OnRxTimeout;
    RadioEvents.RxError = OnRxError;

    Radio.Init(&RadioEvents);
    Radio.SetChannel(RF_FREQUENCY);
    Radio.SetTxConfig(MODEM_LORA, TX_OUTPUT_POWER, 0, LORA_BANDWIDTH,
        LORA_SPREADING_FACTOR, LORA_CODINGRATE,
        LORA_PREAMBLE_LENGTH, LORA_FIX_LENGTH_PAYLOAD_ON,
        true, 0, 0, LORA_IQ_INVERSION_ON, 3000);
    Radio.SetRxConfig(MODEM_LORA, LORA_BANDWIDTH, LORA_SPREADING_FACTOR,
        LORA_CODINGRATE, 0, LORA_PREAMBLE_LENGTH,
        LORA_SYMBOL_TIMEOUT, LORA_FIX_LENGTH_PAYLOAD_ON,
        0, true, 0, 0, LORA_IQ_INVERSION_ON, true);

    printf("System Ready.\n");
    printf("UI: Draw Screen 1\n");

    while (1) {
        // 1. 화면 그리기 & 로직 실행
        if (needsRedraw) {
            needsRedraw = 0;
            switch (currentState) {
            case SCREEN_START:       Draw_Screen_Start(); QueryLevels(); break;
            case SCREEN_MOOD_SELECT: Draw_Screen_MoodSelect(); break;
            case SCREEN_CONFIRM:     Draw_Screen_Confirm(selectedMood); break;
            case SCREEN_BLENDING:
                Draw_Screen_Blending();
                RunBlendingProcess(selectedMood);   // 선택된 무드에 맞게 모터 + LoRa 동작
                break;
            case SCREEN_FINISH:      Draw_Screen_Finish(); break;
            }
        }

        // 2. 터치 감지
        if (currentState != SCREEN_BLENDING) {
            uint8_t pb7 = HAL_GPIO_ReadPin(GPIOB, GPIO_PIN_7);
            if (pb7 == GPIO_PIN_RESET) {
                if (HAL_GetTick() - lastTouchTime > 200) {
                    HAL_Delay(20);
                    if (HAL_GPIO_ReadPin(GPIOB, GPIO_PIN_7) == GPIO_PIN_RESET) {
                        HAL_Delay(10);
                        uint8_t touchData = LCD_SendTouchRequest();
                        if (touchData != 0) {
                            ProcessTouch(touchData);
                            lastTouchTime = HAL_GetTick();
                        }
                    }
                }
            }
            lastEventState = pb7;
        }

        // ★ 기존의 menu/스위치(LavenderMove/CedarwoodMove 호출 부분)는 삭제함

        // 3. [추가] 시작 화면에서 기다리는 동안 주기적으로 향료 통 수위 확인
        if (currentState == SCREEN_START && !needsRedraw &&
            HAL_GetTick() - lastLevelQuery > LEVEL_QUERY_INTERVAL_MS) {
            QueryLevels();
        }

        HAL_Delay(10);
    }
}

/* USER CODE BEGIN 4 */
void OnTxDone(void) {
    Radio.Sleep();
    // 전송 후 RX로 갈지 말지는 로직에 따라 다름
    State = IDLE;
}

void OnRxDone(uint8_t* payload, uint16_t size, int16_t rssi, int8_t snr)
{
    Radio.Sleep();
    BufferSize = size;
    memcpy(Buffer, payload, BufferSize);
    RssiValue = rssi;
    SnrValue = snr;
    State = RX;

    // 로직을 간결하게 수정
    if (Buffer[0] == Rx_ID)
    {
        // 수신된 페이로드 (ID 제외)가 "DONE" 문자열인지 확인
        if (size >= 5 && strncmp((char*)Buffer + 1, "DONE", 4) == 0) { // ★ strcmp -> strncmp
            lora_ok_flag = 1; // OK 플래그 설정
            printf("OnRxDone: OK/DONE message received.\n");
        }
        else {
            // 다른 Rx_ID 패킷이거나, DONE이 아닌 메시지 수신
            printf("OnRxDone: RX but not DONE\n");
        }
    }
}

void OnTxTimeout(void) { Radio.Sleep(); State = IDLE; }
void OnRxTimeout(void) { Radio.Sleep(); State = RX_TIMEOUT; } // 필요시 RX 재진입 로직 추가
void OnRxError(void) { Radio.Sleep(); State = RX_ERROR; }
/* USER CODE END 4 */

void SystemClock_Config(void)
{
    RCC_OscInitTypeDef RCC_OscInitStruct = { 0 };
    RCC_ClkInitTypeDef RCC_ClkInitStruct = { 0 };
    __HAL_RCC_PWR_CLK_ENABLE();
    __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE3);
    RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSI;
    RCC_OscInitStruct.HSIState = RCC_HSI_ON;
    RCC_OscInitStruct.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
    RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
    RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSI;
    RCC_OscInitStruct.PLL.PLLM = 16;
    RCC_OscInitStruct.PLL.PLLN = 336;
    RCC_OscInitStruct.PLL.PLLP = RCC_PLLP_DIV4;
    RCC_OscInitStruct.PLL.PLLQ = 2;
    RCC_OscInitStruct.PLL.PLLR = 2;
    HAL_RCC_OscConfig(&RCC_OscInitStruct);
    RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_SYSCLK
        | RCC_CLOCKTYPE_PCLK1 | RCC_CLOCKTYPE_PCLK2;
    RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
    RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
    RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV2;
    RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;
    HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_2);
}
static void MX_SPI1_Init(void)
{
    hspi1.Instance = SPI1;
    hspi1.Init.Mode = SPI_MODE_MASTER;
    hspi1.Init.Direction = SPI_DIRECTION_2LINES;
    hspi1.Init.DataSize = SPI_DATASIZE_8BIT;
    hspi1.Init.CLKPolarity = SPI_POLARITY_LOW;
    hspi1.Init.CLKPhase = SPI_PHASE_1EDGE;
    hspi1.Init.NSS = SPI_NSS_SOFT;
    hspi1.Init.BaudRatePrescaler = SPI_BAUDRATEPRESCALER_128;
    hspi1.Init.FirstBit = SPI_FIRSTBIT_MSB;
    hspi1.Init.TIMode = SPI_TIMODE_DISABLE;
    hspi1.Init.CRCCalculation = SPI_CRCCALCULATION_DISABLE;
    hspi1.Init.CRCPolynomial = 10;
    HAL_SPI_Init(&hspi1);
}
static void MX_TIM2_Init(void)
{
    TIM_ClockConfigTypeDef sClockSourceConfig = { 0 };
    TIM_MasterConfigTypeDef sMasterConfig = { 0 };
    htim2.Instance = TIM2;
    htim2.Init.Prescaler = 84 - 1;
    htim2.Init.CounterMode = TIM_COUNTERMODE_UP;
    htim2.Init.Period = 999;
    htim2.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
    htim2.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
    HAL_TIM_Base_Init(&htim2);
    sClockSourceConfig.ClockSource = TIM_CLOCKSOURCE_INTERNAL;
    HAL_TIM_ConfigClockSource(&htim2, &sClockSourceConfig);
    sMasterConfig.MasterOutputTrigger = TIM_TRGO_RESET;
    sMasterConfig.MasterSlaveMode = TIM_MASTERSLAVEMODE_DISABLE;
    HAL_TIMEx_MasterConfigSynchronization(&htim2, &sMasterConfig);
}
static void MX_USART2_UART_Init(void)
{
    huart2.Instance = USART2;
    huart2.Init.BaudRate = 115200;
    huart2.Init.WordLength = UART_WORDLENGTH_8B;
    huart2.Init.StopBits = UART_STOPBITS_1;
    huart2.Init.Parity = UART_PARITY_NONE;
    huart2.Init.Mode = UART_MODE_TX_RX;
    huart2.Init.HwFlowCtl = UART_HWCONTROL_NONE;
    huart2.Init.OverSampling = UART_OVERSAMPLING_16;
    HAL_UART_Init(&huart2);
}
static void MX_USART3_UART_Init(void)
{
    huart3.Instance = USART3;
    huart3.Init.BaudRate = 57600;
    huart3.Init.WordLength = UART_WORDLENGTH_8B;
    huart3.Init.StopBits = UART_STOPBITS_1;
    huart3.Init.Parity = UART_PARITY_NONE;
    huart3.Init.Mode = UART_MODE_TX_RX;
    huart3.Init.HwFlowCtl = UART_HWCONTROL_NONE;
    huart3.Init.OverSampling = UART_OVERSAMPLING_16;
    HAL_UART_Init(&huart3);
}
static void MX_GPIO_Init(void)
{
    GPIO_InitTypeDef GPIO_InitStruct = { 0 };
    __HAL_RCC_GPIOC_CLK_ENABLE();
    __HAL_RCC_GPIOH_CLK_ENABLE();
    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();
    HAL_GPIO_WritePin(GPIOC, RADIO_ANT_SWITCH_Pin | LED_2_Pin, GPIO_PIN_RESET);
    HAL_GPIO_WritePin(RADIO_RESET_GPIO_Port, RADIO_RESET_Pin, GPIO_PIN_SET);
    HAL_GPIO_WritePin(LED_1_GPIO_Port, LED_1_Pin, GPIO_PIN_RESET);
    HAL_GPIO_WritePin(RADIO_NSS_GPIO_Port, RADIO_NSS_Pin, GPIO_PIN_SET);
    GPIO_InitStruct.Pin = B1_Pin;
    GPIO_InitStruct.Mode = GPIO_MODE_IT_FALLING;
    GPIO_InitStruct.Pull = GPIO_NOPULL;
    HAL_GPIO_Init(B1_GPIO_Port, &GPIO_InitStruct);
    GPIO_InitStruct.Pin = RADIO_ANT_SWITCH_Pin;
    GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
    GPIO_InitStruct.Pull = GPIO_PULLUP;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(RADIO_ANT_SWITCH_GPIO_Port, &GPIO_InitStruct);
    GPIO_InitStruct.Pin = RADIO_RESET_Pin | LED_2_Pin;
    GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
    GPIO_InitStruct.Pull = GPIO_NOPULL;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GPIOC, &GPIO_InitStruct);
    GPIO_InitStruct.Pin = LED_1_Pin;
    GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
    GPIO_InitStruct.Pull = GPIO_NOPULL;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(LED_1_GPIO_Port, &GPIO_InitStruct);
    GPIO_InitStruct.Pin = RADIO_DIO_0_Pin;
    GPIO_InitStruct.Mode = GPIO_MODE_IT_RISING;
    GPIO_InitStruct.Pull = GPIO_NOPULL;
    HAL_GPIO_Init(RADIO_DIO_0_GPIO_Port, &GPIO_InitStruct);
    GPIO_InitStruct.Pin = RADIO_DIO_1_Pin;
    GPIO_InitStruct.Mode = GPIO_MODE_IT_RISING;
    GPIO_InitStruct.Pull = GPIO_NOPULL;
    HAL_GPIO_Init(RADIO_DIO_1_GPIO_Port, &GPIO_InitStruct);
    GPIO_InitStruct.Pin = RADIO_NSS_Pin;
    GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
    GPIO_InitStruct.Pull = GPIO_NOPULL;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(RADIO_NSS_GPIO_Port, &GPIO_InitStruct);
    GPIO_InitStruct.Pin = GPIO_PIN_7;
    GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
    GPIO_InitStruct.Pull = GPIO_PULLUP;
    HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);
    GPIO_InitStruct.Pin = GPIO_PIN_9;
    GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
    GPIO_InitStruct.Pull = GPIO_NOPULL;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);
    GPIO_InitStruct.Pin = GPIO_PIN_10 | GPIO_PIN_4 | GPIO_PIN_5;
    HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);
    GPIO_InitStruct.Pin = GPIO_PIN_12 | GPIO_PIN_15;
    GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
    GPIO_InitStruct.Pull = GPIO_PULLUP;
    HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);
    HAL_NVIC_SetPriority(EXTI3_IRQn, 0, 0);
    HAL_NVIC_EnableIRQ(EXTI3_IRQn);
    HAL_NVIC_SetPriority(EXTI15_10_IRQn, 0, 0);
    HAL_NVIC_EnableIRQ(EXTI15_10_IRQn);
}

void Error_Handler(void)
{
    __disable_irq();
    while (1)
    {
    }
}

#ifdef USE_FULL_ASSERT
void assert_failed(uint8_t* file, uint32_t line)
{
}
#endif /* USE_FULL_ASSERT */
