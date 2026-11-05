/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2025 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "main.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include <string.h>
#include <stdarg.h>
#include <stdio.h>
#include "sx1272/radio.h"
#include <stdlib.h>
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */
uint8_t halfstep_seq[8][4] = {
  {1,0,0,0},
  {1,1,0,0},
  {0,1,0,0},
  {0,1,1,0},
  {0,0,1,0},
  {0,0,1,1},
  {0,0,0,1},
  {1,0,0,1}
};

typedef enum
{
	LOWPOWER = 0,
	IDLE,
	RX,
	RX_TIMEOUT,
	RX_ERROR,
	TX,
	TX_TIMEOUT
}States_t;

typedef struct
{
    int sensor_id;      // 센서 번호
    float rotation_ml; // 회전값 (ml)
} StepingMotor_t;




// [추가] 향료 통 수위 센서 하나 (port 가 NULL 이면 센서 없음)
typedef struct
{
    GPIO_TypeDef *port;
    uint16_t pin;
} LevelSensor_t;
/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */
#define Prox_Port GPIOB
#define Prox_Pin GPIO_PIN_2

#define ONE_CYCLE 4096
#define QUARTER_CYCLE 1028


#define RF_FREQUENCY                                922100000 // Hz
#define TX_OUTPUT_POWER                             14        // dBm
#define LORA_BANDWIDTH                              0         // [0: 125 kHz,
                                                              //  1: 250 kHz,
                                                              //  2: 500 kHz,
                                                              //  3: Reserved]
#define LORA_SPREADING_FACTOR                       7         // [SF7..SF12]
#define LORA_CODINGRATE                             1         // [1: 4/5,
                                                              //  2: 4/6,
                                                              //  3: 4/7,
                                                              //  4: 4/8]
#define LORA_PREAMBLE_LENGTH                        8         // Same for Tx and Rx
#define LORA_SYMBOL_TIMEOUT                         0         // Symbols
#define LORA_FIX_LENGTH_PAYLOAD_ON                  false
#define LORA_IQ_INVERSION_ON                        false
#define RX_TIMEOUT_VALUE                            1000
#define BUFFER_SIZE                                 64 		// Define the payload size here

#define Rx_ID			121		// 공유 아이디 — 메인보드 PACKET_ID(121)와 같아야 통신됨 (기존 20 → 121)
#define PHYMAC_PDUOFFSET_RXID          				0		// packet 내부 아이디 offset
/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/
SPI_HandleTypeDef hspi1;

TIM_HandleTypeDef htim2;

UART_HandleTypeDef huart2;

/* USER CODE BEGIN PV */
//// 작업 큐를 위한 전역 변수 추가
//#define JOB_QUEUE_SIZE 10 // 최대 10개 작업
//StepingMotor_t g_jobQueue[JOB_QUEUE_SIZE]; // 작업 목록 배열
//int g_jobTotal = 0;   // 전송할 총 작업 수
//int g_jobIndex = 0;   // 현재 전송 중인 작업 인덱스

uint16_t BufferSize = BUFFER_SIZE;
uint8_t Buffer[BUFFER_SIZE];
//const uint8_t HelloMsg[] = "HELLO";

States_t State = RX; // TX or RX

int8_t RssiValue = 0;
int8_t SnrValue = 0;

/*!
 * Radio events function pointer
 */
static RadioEvents_t RadioEvents;

// [추가] 받은 작업은 인터럽트 안에서 바로 처리하지 않고 메인 루프에서 처리한다.
//  LoRa 수신 콜백(OnRxDone)은 GPIO 인터럽트(EXTI, 우선순위 0) 안에서 불리는데 SysTick 도 우선순위 0 이라,
//  인터럽트 안에서 모터를 돌리면 HAL_Delay 가 끝나지 않아 보드가 멈춘다.
volatile uint8_t g_job_pending = 0;
StepingMotor_t g_job;

// [추가] 향료 통 수위 센서 표 (index = sensor_id, 1 Lavender 2 Cedarwood 3 Vanilla 4 Bergamot)
//  센서를 더 달면 해당 칸에 { 포트, 핀 } 을 넣고, 그 핀을 CubeMX 에서 GPIO_Input 으로 설정한다.
static const LevelSensor_t LEVEL_SENSORS[5] = {
    { NULL, 0 },                    // 0: 사용 안 함
    { Prox_GPIO_Port, Prox_Pin },   // 1: Lavender — CubeMX 에 'Prox'(PB2) 로 설정된 센서
    { NULL, 0 },                    // 2: Cedarwood
    { NULL, 0 },                    // 3: Vanilla
    { NULL, 0 },                    // 4: Bergamot
};
#define LEVEL_LIQUID_STATE  GPIO_PIN_RESET  // 기존 테스트 코드 기준: RESET 이면 "water on"(액체 감지)
#define LEVEL_LOW           0
#define LEVEL_OK            1
#define LEVEL_UNKNOWN       0xFF
/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_USART2_UART_Init(void);
static void MX_SPI1_Init(void);
static void MX_TIM2_Init(void);
/* USER CODE BEGIN PFP */

void set_coils(int motor_id, uint8_t a, uint8_t b, uint8_t c, uint8_t d);
void step_steps(int motor_id, int steps, int delay_ms);
void step_delay_ms(uint32_t ms);

/*!
 * \brief Function to be executed on Radio Tx Done event
 */
void OnTxDone( void );

/*!
 * \brief Function to be executed on Radio Rx Done event
 */
void OnRxDone( uint8_t *payload, uint16_t size, int16_t rssi, int8_t snr );

/*!
 * \brief Function executed on Radio Tx Timeout event
 */
void OnTxTimeout( void );

/*!
 * \brief Function executed on Radio Rx Timeout event
 */
void OnRxTimeout( void );

/*!
 * \brief Function executed on Radio Rx Error event
 */
void OnRxError( void );

int __io_putchar(int ch);
//void Debug_Printf(const char *format, ...);
uint8_t ReadLevel(int sensor_id);
void RunJob(const StepingMotor_t *job);
void ExtraMotorPins_Init(void);
/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */

/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{

  /* USER CODE BEGIN 1 */

  /* USER CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/

  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();

  /* USER CODE BEGIN Init */

  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER CODE BEGIN SysInit */

  /* USER CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  MX_USART2_UART_Init();
  MX_SPI1_Init();
  MX_TIM2_Init();
  /* USER CODE BEGIN 2 */
  // Radio initialization
  RadioEvents.TxDone = OnTxDone;
  RadioEvents.RxDone = OnRxDone;
  RadioEvents.TxTimeout = OnTxTimeout;
  RadioEvents.RxTimeout = OnRxTimeout;
  RadioEvents.RxError = OnRxError;

  Radio.Init( &RadioEvents );


  Radio.SetChannel( RF_FREQUENCY );
  Radio.SetTxConfig( MODEM_LORA, TX_OUTPUT_POWER, 0, LORA_BANDWIDTH,
									 LORA_SPREADING_FACTOR, LORA_CODINGRATE,
									 LORA_PREAMBLE_LENGTH, LORA_FIX_LENGTH_PAYLOAD_ON,
									 true, 0, 0, LORA_IQ_INVERSION_ON, 3000 );

  Radio.SetRxConfig( MODEM_LORA, LORA_BANDWIDTH, LORA_SPREADING_FACTOR,
									 LORA_CODINGRATE, 0, LORA_PREAMBLE_LENGTH,
									 LORA_SYMBOL_TIMEOUT, LORA_FIX_LENGTH_PAYLOAD_ON,
									 0, true, 0, 0, LORA_IQ_INVERSION_ON, true );

  Buffer[PHYMAC_PDUOFFSET_RXID] = Rx_ID;
  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {
//	  if(HAL_GPIO_ReadPin(Prox_Port, Prox_Pin) == GPIO_PIN_RESET){
//	      printf("water on\n");   // 물 감지됨
//	  }else{
//	      printf("water off\n");  // 물 없음
//	  }
//	  HAL_Delay(1000);

	  // [추가] 수신한 작업을 여기서(인터럽트 밖에서) 실행
	  if (g_job_pending)
	  {
		  StepingMotor_t job = g_job;
		  g_job_pending = 0;
		  RunJob(&job);
	  }


	  switch (State) {
		  case IDLE:
			  break;
		  case RX:
			  // "작업(Job)을 기다립니다..."
			  printf("Waiting for Job...\n\r");
			  Radio.Rx(RX_TIMEOUT_VALUE); // LoRa 수신 모드 켜기
			  State = IDLE; // 수신이 완료/에러/타임아웃될 때까지 IDLE로 대기
			  break;
		  default:
			  State = IDLE;
		  break;
	  }

	  // 짧은 지연으로 CPU 사용률 조절 (선택사항)
	  HAL_Delay(1);
    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */
  }
  /* USER CODE END 3 */
}

/**
  * @brief System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

  /** Configure the main internal regulator output voltage
  */
  __HAL_RCC_PWR_CLK_ENABLE();
  __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE3);

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSE;
  RCC_OscInitStruct.HSEState = RCC_HSE_ON;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSE;
  RCC_OscInitStruct.PLL.PLLM = 4;
  RCC_OscInitStruct.PLL.PLLN = 50;
  RCC_OscInitStruct.PLL.PLLP = RCC_PLLP_DIV2;
  RCC_OscInitStruct.PLL.PLLQ = 2;
  RCC_OscInitStruct.PLL.PLLR = 2;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the CPU, AHB and APB buses clocks
  */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV2;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_1) != HAL_OK)
  {
    Error_Handler();
  }
}

/**
  * @brief SPI1 Initialization Function
  * @param None
  * @retval None
  */
static void MX_SPI1_Init(void)
{

  /* USER CODE BEGIN SPI1_Init 0 */

  /* USER CODE END SPI1_Init 0 */

  /* USER CODE BEGIN SPI1_Init 1 */

  /* USER CODE END SPI1_Init 1 */
  /* SPI1 parameter configuration*/
  hspi1.Instance = SPI1;
  hspi1.Init.Mode = SPI_MODE_MASTER;
  hspi1.Init.Direction = SPI_DIRECTION_2LINES;
  hspi1.Init.DataSize = SPI_DATASIZE_8BIT;
  hspi1.Init.CLKPolarity = SPI_POLARITY_LOW;
  hspi1.Init.CLKPhase = SPI_PHASE_1EDGE;
  hspi1.Init.NSS = SPI_NSS_SOFT;
  hspi1.Init.BaudRatePrescaler = SPI_BAUDRATEPRESCALER_64;
  hspi1.Init.FirstBit = SPI_FIRSTBIT_MSB;
  hspi1.Init.TIMode = SPI_TIMODE_DISABLE;
  hspi1.Init.CRCCalculation = SPI_CRCCALCULATION_DISABLE;
  hspi1.Init.CRCPolynomial = 10;
  if (HAL_SPI_Init(&hspi1) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN SPI1_Init 2 */

  /* USER CODE END SPI1_Init 2 */

}

/**
  * @brief TIM2 Initialization Function
  * @param None
  * @retval None
  */
static void MX_TIM2_Init(void)
{

  /* USER CODE BEGIN TIM2_Init 0 */

  /* USER CODE END TIM2_Init 0 */

  TIM_ClockConfigTypeDef sClockSourceConfig = {0};
  TIM_MasterConfigTypeDef sMasterConfig = {0};

  /* USER CODE BEGIN TIM2_Init 1 */

  /* USER CODE END TIM2_Init 1 */
  htim2.Instance = TIM2;
  htim2.Init.Prescaler = 49;
  htim2.Init.CounterMode = TIM_COUNTERMODE_UP;
  htim2.Init.Period = 4294967295;
  htim2.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
  htim2.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
  if (HAL_TIM_Base_Init(&htim2) != HAL_OK)
  {
    Error_Handler();
  }
  sClockSourceConfig.ClockSource = TIM_CLOCKSOURCE_INTERNAL;
  if (HAL_TIM_ConfigClockSource(&htim2, &sClockSourceConfig) != HAL_OK)
  {
    Error_Handler();
  }
  sMasterConfig.MasterOutputTrigger = TIM_TRGO_RESET;
  sMasterConfig.MasterSlaveMode = TIM_MASTERSLAVEMODE_DISABLE;
  if (HAL_TIMEx_MasterConfigSynchronization(&htim2, &sMasterConfig) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN TIM2_Init 2 */

  /* USER CODE END TIM2_Init 2 */

}

/**
  * @brief USART2 Initialization Function
  * @param None
  * @retval None
  */
static void MX_USART2_UART_Init(void)
{

  /* USER CODE BEGIN USART2_Init 0 */

  /* USER CODE END USART2_Init 0 */

  /* USER CODE BEGIN USART2_Init 1 */

  /* USER CODE END USART2_Init 1 */
  huart2.Instance = USART2;
  huart2.Init.BaudRate = 115200;
  huart2.Init.WordLength = UART_WORDLENGTH_8B;
  huart2.Init.StopBits = UART_STOPBITS_1;
  huart2.Init.Parity = UART_PARITY_NONE;
  huart2.Init.Mode = UART_MODE_TX_RX;
  huart2.Init.HwFlowCtl = UART_HWCONTROL_NONE;
  huart2.Init.OverSampling = UART_OVERSAMPLING_16;
  if (HAL_UART_Init(&huart2) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN USART2_Init 2 */

  /* USER CODE END USART2_Init 2 */

}

/**
  * @brief GPIO Initialization Function
  * @param None
  * @retval None
  */
static void MX_GPIO_Init(void)
{
  GPIO_InitTypeDef GPIO_InitStruct = {0};
  /* USER CODE BEGIN MX_GPIO_Init_1 */

  /* USER CODE END MX_GPIO_Init_1 */

  /* GPIO Ports Clock Enable */
  __HAL_RCC_GPIOC_CLK_ENABLE();
  __HAL_RCC_GPIOH_CLK_ENABLE();
  __HAL_RCC_GPIOA_CLK_ENABLE();
  __HAL_RCC_GPIOB_CLK_ENABLE();

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(GPIOC, RADIO_ANT_SWITCH_Pin|LED_2_Pin, GPIO_PIN_RESET);

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(RADIO_RESET_GPIO_Port, RADIO_RESET_Pin, GPIO_PIN_SET);

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(GPIOB, GPIO_PIN_1|GPIO_PIN_13|GPIO_PIN_14|GPIO_PIN_15, GPIO_PIN_RESET);

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(LED_1_GPIO_Port, LED_1_Pin, GPIO_PIN_RESET);

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(RADIO_NSS_GPIO_Port, RADIO_NSS_Pin, GPIO_PIN_SET);

  /*Configure GPIO pin : B1_Pin */
  GPIO_InitStruct.Pin = B1_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_IT_FALLING;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  HAL_GPIO_Init(B1_GPIO_Port, &GPIO_InitStruct);

  /*Configure GPIO pin : RADIO_ANT_SWITCH_Pin */
  GPIO_InitStruct.Pin = RADIO_ANT_SWITCH_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_PULLUP;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(RADIO_ANT_SWITCH_GPIO_Port, &GPIO_InitStruct);

  /*Configure GPIO pins : RADIO_RESET_Pin LED_2_Pin */
  GPIO_InitStruct.Pin = RADIO_RESET_Pin|LED_2_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(GPIOC, &GPIO_InitStruct);

  /*Configure GPIO pins : PB1 PB13 PB14 PB15
                           RADIO_NSS_Pin */
  GPIO_InitStruct.Pin = GPIO_PIN_1|GPIO_PIN_13|GPIO_PIN_14|GPIO_PIN_15
                          |RADIO_NSS_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_HIGH;
  HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);

  /*Configure GPIO pin : Prox_Pin */
  GPIO_InitStruct.Pin = Prox_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  HAL_GPIO_Init(Prox_GPIO_Port, &GPIO_InitStruct);

  /*Configure GPIO pin : LED_1_Pin */
  GPIO_InitStruct.Pin = LED_1_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(LED_1_GPIO_Port, &GPIO_InitStruct);

  /*Configure GPIO pin : RADIO_DIO_0_Pin */
  GPIO_InitStruct.Pin = RADIO_DIO_0_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_IT_RISING;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  HAL_GPIO_Init(RADIO_DIO_0_GPIO_Port, &GPIO_InitStruct);

  /*Configure GPIO pin : RADIO_DIO_1_Pin */
  GPIO_InitStruct.Pin = RADIO_DIO_1_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_IT_RISING;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  HAL_GPIO_Init(RADIO_DIO_1_GPIO_Port, &GPIO_InitStruct);

  /* EXTI interrupt init*/
  HAL_NVIC_SetPriority(EXTI3_IRQn, 0, 0);
  HAL_NVIC_EnableIRQ(EXTI3_IRQn);

  HAL_NVIC_SetPriority(EXTI15_10_IRQn, 0, 0);
  HAL_NVIC_EnableIRQ(EXTI15_10_IRQn);

  /* USER CODE BEGIN MX_GPIO_Init_2 */
  ExtraMotorPins_Init();

  /* USER CODE END MX_GPIO_Init_2 */
}

/* USER CODE BEGIN 4 */
/*

Lavender : Cedarwood : Vanilla : Bergamot


				Cedarwood(2)
	Lavender(1)				Vanilla(3)
				Bergamot(4)
			     bottle

 *
 */



// 모터별 코일 핀 — sub-board/README.md 의 핀맵
typedef struct { GPIO_TypeDef *port; uint16_t pin; } CoilPin_t;
static const CoilPin_t MOTOR_PINS[5][4] = {
    { {0} },                                                                                    // 0: 사용 안 함
    { {GPIOB, GPIO_PIN_13}, {GPIOB, GPIO_PIN_14}, {GPIOB, GPIO_PIN_15}, {GPIOB, GPIO_PIN_1}  }, // 1: Lavender
    { {GPIOB, GPIO_PIN_12}, {GPIOA, GPIO_PIN_11}, {GPIOA, GPIO_PIN_12}, {GPIOC, GPIO_PIN_5}  }, // 2: Cedarwood
    { {GPIOC, GPIO_PIN_3},  {GPIOC, GPIO_PIN_2},  {GPIOB, GPIO_PIN_0},  {GPIOA, GPIO_PIN_4}  }, // 3: Vanilla
    { {GPIOC, GPIO_PIN_12}, {GPIOC, GPIO_PIN_10}, {GPIOD, GPIO_PIN_2},  {GPIOC, GPIO_PIN_11} }, // 4: Bergamot
};

// [추가] 모터 2~4번 핀을 출력으로 설정 (모터 1번 핀은 CubeMX 가 이미 설정함)
void ExtraMotorPins_Init(void){
  GPIO_InitTypeDef init = {0};
  __HAL_RCC_GPIOD_CLK_ENABLE();  // PD2 (모터 4)
  init.Mode = GPIO_MODE_OUTPUT_PP;
  init.Pull = GPIO_NOPULL;
  init.Speed = GPIO_SPEED_FREQ_LOW;
  for (int m = 2; m <= 4; m++) {
    for (int i = 0; i < 4; i++) {
      HAL_GPIO_WritePin(MOTOR_PINS[m][i].port, MOTOR_PINS[m][i].pin, GPIO_PIN_RESET);
      init.Pin = MOTOR_PINS[m][i].pin;
      HAL_GPIO_Init(MOTOR_PINS[m][i].port, &init);
    }
  }
}

void set_coils(int motor_id, uint8_t a, uint8_t b, uint8_t c, uint8_t d){
  if (motor_id < 1 || motor_id > 4) return;
  const uint8_t v[4] = { a, b, c, d };
  for (int i = 0; i < 4; i++) {
    HAL_GPIO_WritePin(MOTOR_PINS[motor_id][i].port, MOTOR_PINS[motor_id][i].pin, v[i] ? GPIO_PIN_SET : GPIO_PIN_RESET);
  }
}

void step_delay_ms(uint32_t ms){
  HAL_Delay(ms); // 간단용도. 정확한 속도 제어는 TIM 사용 권장
}

void step_steps(int motor_id, int steps, int delay_ms){
  static int idx[5] = {0};  // 모터마다 마지막 스텝 위치를 기억 (매번 0부터 시작하면 첫 스텝이 튈 수 있음)
  if (motor_id < 1 || motor_id > 4) return;
  for(int s=0; s<abs(steps); ++s){
    idx[motor_id] = (steps > 0) ? (idx[motor_id] + 1) % 8 : (idx[motor_id] + 7) % 8; // 음수면 역회전
    set_coils( motor_id, halfstep_seq[idx[motor_id]][0], halfstep_seq[idx[motor_id]][1],
                   halfstep_seq[idx[motor_id]][2], halfstep_seq[idx[motor_id]][3] );
    step_delay_ms(delay_ms);
  }
  set_coils(motor_id, 0, 0, 0, 0);  // 다 돌면 코일 전류를 끊어 모터·드라이버 발열 방지
}

// [추가] 수위 센서 읽기
uint8_t ReadLevel(int sensor_id){
  if (sensor_id < 1 || sensor_id > 4 || LEVEL_SENSORS[sensor_id].port == NULL) return LEVEL_UNKNOWN;
  return (HAL_GPIO_ReadPin(LEVEL_SENSORS[sensor_id].port, LEVEL_SENSORS[sensor_id].pin) == LEVEL_LIQUID_STATE)
         ? LEVEL_OK : LEVEL_LOW;
}

// [추가] 작업 하나 실행 후 응답
//  향료 부족 → [ID]"LOW"[sensor_id]       (5바이트) — 모터를 돌리지 않음
//  완료      → [ID]"DONE"[주입 후 수위]    (6바이트) — 수위: 1 충분 / 0 부족 / 0xFF 센서 없음
//  (메인보드는 앞 5바이트로 DONE 을 판단하므로 예전 메인보드 코드와도 호환됨)
void RunJob(const StepingMotor_t *job){
  uint8_t reply[6];
  reply[0] = Rx_ID;

  if (ReadLevel(job->sensor_id) == LEVEL_LOW) {
    printf("> Job refused: sensor %d is LOW\n\r", job->sensor_id);
    memcpy(reply + 1, "LOW", 3);
    reply[4] = (uint8_t)job->sensor_id;
    Radio.Send(reply, 5);
    return;
  }

  int steps = (int)(job->rotation_ml * ONE_CYCLE);
  printf("> Job: sensor %d, %d steps\n\r", job->sensor_id, steps);
  step_steps(job->sensor_id, steps, 1);

  memcpy(reply + 1, "DONE", 4);
  reply[5] = ReadLevel(job->sensor_id);
  Radio.Send(reply, 6);
}

void OnTxDone( void )
{
    Radio.Sleep( );

    State = RX;
    printf("'DONE' sent. Waiting for next command.\n\r");
}

void OnRxDone( uint8_t *payload, uint16_t size, int16_t rssi, int8_t snr )
{
    Radio.Sleep( );
    BufferSize = size;
    memcpy( Buffer, payload, BufferSize );
    RssiValue = rssi;
    SnrValue = snr;

    // 내 ID 이고 작업 패킷 크기가 맞을 때만 작업으로 받는다 (START 패킷 등은 무시)
    if (Buffer[PHYMAC_PDUOFFSET_RXID] == Rx_ID && BufferSize == (1 + sizeof(StepingMotor_t)) && !g_job_pending)
    {
        memcpy(&g_job, Buffer + 1, sizeof(StepingMotor_t));
        g_job_pending = 1;  // 실제 동작은 메인 루프에서 (인터럽트 안에서 HAL_Delay 금지)
        State = IDLE;       // 응답을 보낼 때까지는 수신 대기 안 함
    }
    else
    {
        State = RX;
    }
}

void OnTxTimeout( void )
{
    Radio.Sleep( );
    State = RX;  // [수정] 기존 값 TX 는 메인 루프에서 IDLE 로 바뀌어 다시는 수신하지 않게 됐음
    printf( "> OnTxTimeout\n");
}

void OnRxTimeout( void )
{
    Radio.Sleep( );
    State = RX;
    printf( "> OnRxTimeout\n");
}

void OnRxError( void )
{
    Radio.Sleep( );
    State = RX;
    printf( "> OnRxError\n");
}

int __io_putchar(int ch) {
	HAL_UART_Transmit(&huart2, (uint8_t*)&ch, 1, HAL_MAX_DELAY);
	return ch;
}

//void Debug_Printf(const char *format, ...) {
//    char buffer[256];
//    va_list args;
//    va_start(args, format);
//    vsnprintf(buffer, sizeof(buffer), format, args);
//    va_end(args);
//    HAL_UART_Transmit(&huart2, (uint8_t*)buffer, strlen(buffer), HAL_MAX_DELAY);
//}

/* USER CODE END 4 */

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
  /* User can add his own implementation to report the HAL error return state */
  __disable_irq();
  while (1)
  {
  }
  /* USER CODE END Error_Handler_Debug */
}
#ifdef USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */
