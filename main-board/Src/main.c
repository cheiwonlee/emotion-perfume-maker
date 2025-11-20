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
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

// motor move valuable
int current_angle = 0;
int Lavender_angle = 0;
int Cedarwood_angle = 90;
int Vanilla_angle = 180;
int Bergamot_angle = 270;
int move_angle = 0;
int value = 0;

volatile uint8_t lora_ok_flag = 0; // check OK message
volatile uint8_t lora_wait_flag = 0; // check wait

typedef struct{
	int sensor_id;
	float rotation_ml;
}StepingMotor_t;
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
/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */
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

#define Rx_ID			7		// 공유 아이디
#define PHYMAC_PDUOFFSET_RXID          				0		// packet 내부 아이디 offset

// Define the GPIO pins connected to IN1, IN2, IN3, IN4(Step motor)
#define IN1_PORT GPIOA
#define IN1_PIN  GPIO_PIN_9
#define IN2_PORT GPIOB
#define IN2_PIN  GPIO_PIN_10
#define IN3_PORT GPIOB
#define IN3_PIN  GPIO_PIN_4
#define IN4_PORT GPIOB
#define IN4_PIN  GPIO_PIN_5

// limit switch
#define LIMIT_SWITCH_PORT GPIOA
#define LIMIT_SWITCH_PIN  GPIO_PIN_12

// Prox
#define Lavender_Prox_PORT GPIOA
#define Lavender_Prox_PIN  GPIO_PIN_15
/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/
SPI_HandleTypeDef hspi1;

TIM_HandleTypeDef htim2;

UART_HandleTypeDef huart2;

/* USER CODE BEGIN PV */
uint16_t BufferSize = BUFFER_SIZE;
uint8_t Buffer[BUFFER_SIZE];
const uint8_t HelloMsg[] = "HELLO";

States_t State = TX; // TX or RX

int8_t RssiValue = 0;
int8_t SnrValue = 0;

/*!
 * Radio events function pointer
 */
static RadioEvents_t RadioEvents;
/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_USART2_UART_Init(void);
static void MX_SPI1_Init(void);
static void MX_TIM2_Init(void);
/* USER CODE BEGIN PFP */

uint16_t PrepareTxPacket(int sensor_id, float rotation_ml)
{
  // 1. 전송할 데이터 구조체 준비
  StepingMotor_t Steping_to_send;
  Steping_to_send.sensor_id = sensor_id;
  Steping_to_send.rotation_ml = rotation_ml;

  // 2. 전역 'Buffer'에 데이터 쓰기
  Buffer[0] = Rx_ID;
  memcpy(Buffer + 1, &Steping_to_send, sizeof(StepingMotor_t));

  // 3. 총 패킷 크기 반환 (ID 1바이트 + 구조체 크기)
  return (1 + sizeof(StepingMotor_t));
}

// Half-Step Sequence (8 steps)
const uint8_t half_step_sequence[8][4] = {
    {1, 0, 0, 0}, // Step 0
    {1, 1, 0, 0}, // Step 1
    {0, 1, 0, 0}, // Step 2
    {0, 1, 1, 0}, // Step 3
    {0, 0, 1, 0}, // Step 4
    {0, 0, 1, 1}, // Step 5
    {0, 0, 0, 1}, // Step 6
    {1, 0, 0, 1}  // Step 7
};

// Function to set the motor control pins
// [핵심 수정] IN2와 IN3의 출력 순서를 바꿈 (b와 c 위치 변경)
void SetMotorPins(uint8_t a, uint8_t b, uint8_t c, uint8_t d) {
    HAL_GPIO_WritePin(IN1_PORT, IN1_PIN, (GPIO_PinState)a); // IN1 <- a
    HAL_GPIO_WritePin(IN2_PORT, IN2_PIN, (GPIO_PinState)b); // IN2 <- b (원래 c였던 입력이 IN2로)
    HAL_GPIO_WritePin(IN3_PORT, IN3_PIN, (GPIO_PinState)c); // IN3 <- c (원래 b였던 입력이 IN3으로)
    HAL_GPIO_WritePin(IN4_PORT, IN4_PIN, (GPIO_PinState)d); // IN4 <- d
}

// Function to move the motor a certain number of steps
// [핵심 수정] HAL_Delay를 사용하여 딜레이를 확보합니다.
void MoveMotorSteps(int steps, int delay_ms) {
    int direction = (steps > 0) ? 1 : -1;
    steps = (steps > 0) ? steps : -steps;

    static int current_step_index = 0; // Current index in the 8-step sequence

    for (int i = 0; i < steps; i++) {
        // Calculate the next step index based on direction
        current_step_index = (current_step_index + direction + 8) % 8;

        // Apply the pin states
        SetMotorPins(
            half_step_sequence[current_step_index][0],
            half_step_sequence[current_step_index][1],
            half_step_sequence[current_step_index][2],
            half_step_sequence[current_step_index][3]
        );

        // *** HAL_Delay(밀리초)를 사용하여 속도 제어 ***
        HAL_Delay(delay_ms);
    }
}

void ResetMotor(){
	printf("PA0 = %d\n", HAL_GPIO_ReadPin(GPIOA, GPIO_PIN_0));
	while(HAL_GPIO_ReadPin(LIMIT_SWITCH_PORT, LIMIT_SWITCH_PIN) == GPIO_PIN_SET){
		MoveMotorSteps(-1, 3);
	}


	SetMotorPins(
			half_step_sequence[0][0],
	        half_step_sequence[0][1],
	        half_step_sequence[0][2],
	        half_step_sequence[0][3]);

	current_angle = 0;

	// 완료 통신할 것인지?
}


// wait OK message
void WaitForLoRaOK_Blocking()
{
    lora_ok_flag = 0;
    lora_wait_flag = 1;
    printf("Waiting for OK...\n");
    // LoRa 수신 시작
    Radio.Rx(RX_TIMEOUT_VALUE);

    // OK가 들어올 때까지 Blocking
    while (lora_ok_flag == 0)
    {
        HAL_Delay(10);
        if(State == RX_TIMEOUT || State == RX_ERROR){
        	Radio.Rx(RX_TIMEOUT_VALUE);
        	State = RX;
        }

    }

    // OK 받음 -> 종료
    lora_wait_flag = 0;
}

// home(angle = 0)
void LavenderMove(float ml){
	move_angle = Lavender_angle - current_angle;
	if(move_angle > 180) move_angle -= 360;
	if(move_angle < -180) move_angle += 360;

	MoveMotorSteps(1024*move_angle/90, 2);
	current_angle = (current_angle + move_angle + 360) % 360;

	// Send a ready message

	uint16_t packetSize = PrepareTxPacket(1, ml);
	StepingMotor_t* ptr = (StepingMotor_t*)(Buffer + 1);
	printf("sensor_id: %d, rotation_ml: %.2f\n", ptr->sensor_id, ptr->rotation_ml);
	Radio.Send(Buffer, packetSize);




	// wait ok msseage
	WaitForLoRaOK_Blocking();
}

void CedarwoodMove(float ml){
	move_angle = Cedarwood_angle - current_angle;
	if(move_angle > 180) move_angle -= 360;
	if(move_angle < -180) move_angle += 360;
	MoveMotorSteps(1024*move_angle/90, 2);
	current_angle = (current_angle + move_angle + 360) % 360;

	// Send a ready message
	uint16_t packetSize = PrepareTxPacket(1, ml);
	StepingMotor_t* ptr = (StepingMotor_t*)(Buffer + 1);
	printf("sensor_id: %d, rotation_ml: %.2f\n", ptr->sensor_id, ptr->rotation_ml);
	Radio.Send(Buffer, packetSize);


	// wait ok msseage
	WaitForLoRaOK_Blocking();
}

void VanillaMove(float ml){
	move_angle = Vanilla_angle - current_angle;
	if(move_angle > 180) move_angle -= 360;
	if(move_angle < -180) move_angle += 360;
	MoveMotorSteps(1024*move_angle/90, 2);
	current_angle = (current_angle + move_angle + 360) % 360;

	// Send a ready message
uint16_t packetSize = PrepareTxPacket(1, ml);
	StepingMotor_t* ptr = (StepingMotor_t*)(Buffer + 1);
	printf("sensor_id: %d, rotation_ml: %.2f\n", ptr->sensor_id, ptr->rotation_ml);
	Radio.Send(Buffer, packetSize);

	// wait ok msseage
	WaitForLoRaOK_Blocking();
}

void BergamotMove(float ml){
	move_angle = Bergamot_angle - current_angle;
	if(move_angle > 180) move_angle -= 360;
	if(move_angle < -180) move_angle += 360;
	MoveMotorSteps(1024*move_angle/90, 2);
	current_angle = (current_angle + move_angle + 360) % 360;

	// Send a ready message
	uint16_t packetSize = PrepareTxPacket(1, ml);
	StepingMotor_t* ptr = (StepingMotor_t*)(Buffer + 1);
	printf("sensor_id: %d, rotation_ml: %.2f\n", ptr->sensor_id, ptr->rotation_ml);
	Radio.Send(Buffer, packetSize);

	// wait ok msseage
	WaitForLoRaOK_Blocking();
}

// 수위 감지되면 0 출력
void ProxCheck(){
	value = HAL_GPIO_ReadPin(Lavender_Prox_PORT, Lavender_Prox_PIN);
	printf("Lavender : %d\r\n", value);
	printf("Cedarwood : %d\r\n", 0);
	printf("Vanilla : %d\r\n", 0);
	printf("Bergamot : %d\r\n", 0);
}


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
  // ResetMotor();
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
	  ProxCheck();
	  HAL_Delay(3000);
	  //MoveMotorSteps(4096, 5);
	   // menu 터치패드로 신호를 받음
//	  switch(menu){
//	  	  case 1: // fresh
//	  		  LavenderMove(2);
//	  		  CedarwoodMove(2);
//	  		  VanillaMove(2);
//	  		  BergamotMove(8);
//	  		  menu = 0;
//	  		  break;
//	  	  case 2: // calm
//	  		  LavenderMove(8);
//	  		  CedarwoodMove(4);
//	   		  VanillaMove(2);
//	   		  BergamotMove(2);
//	   		  menu = 0;
//	   		  break;
//	  	  case 3: // confident
//	  		  LavenderMove(2);
//	  		  CedarwoodMove(6);
//	  		  VanillaMove(2);
//	  		  BergamotMove(4);
//	  		  menu = 0;
//	  		  break;
//	  	  case 4: // sweet & romantic
//	  		  LavenderMove(4);
//	  		  CedarwoodMove(2);
//	  		  VanillaMove(8);
//	  		  BergamotMove(2);
//	  		  menu = 0;
//	  		  break;
//	  	  case 5: // energetic
//	  		  LavenderMove(2);
//	  		  CedarwoodMove(2);
//	  		  VanillaMove(2);
//	  		  BergamotMove(10);
//	  		  menu = 0;
//	  		  break;
//	  	  case 6: // cozy
//	  		  LavenderMove(4);
//	  		  CedarwoodMove(4);
//	  		  VanillaMove(8);
//	  		  BergamotMove(2);
//	  		  menu = 0;
//	  		  break;
//	  	  case 7: // deep & mystic
//	  		  LavenderMove(1);
//	  		  CedarwoodMove(4);
//	  		  VanillaMove(1);
//	  		  BergamotMove(1);
//	  		  menu = 0;
//	  		  break;
//	  }


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
  htim2.Init.Prescaler = 50-1;
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
  HAL_GPIO_WritePin(GPIOB, GPIO_PIN_10|GPIO_PIN_4|GPIO_PIN_5, GPIO_PIN_RESET);

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(GPIOA, LED_1_Pin|GPIO_PIN_9, GPIO_PIN_RESET);

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

  /*Configure GPIO pins : PA0 PA12 PA15 */
  GPIO_InitStruct.Pin = GPIO_PIN_0|GPIO_PIN_12|GPIO_PIN_15;
  GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
  GPIO_InitStruct.Pull = GPIO_PULLUP;
  HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);

  /*Configure GPIO pins : PB10 PB4 PB5 */
  GPIO_InitStruct.Pin = GPIO_PIN_10|GPIO_PIN_4|GPIO_PIN_5;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);

  /*Configure GPIO pins : LED_1_Pin PA9 */
  GPIO_InitStruct.Pin = LED_1_Pin|GPIO_PIN_9;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);

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

  /*Configure GPIO pin : RADIO_NSS_Pin */
  GPIO_InitStruct.Pin = RADIO_NSS_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_HIGH;
  HAL_GPIO_Init(RADIO_NSS_GPIO_Port, &GPIO_InitStruct);

  /* EXTI interrupt init*/
  HAL_NVIC_SetPriority(EXTI3_IRQn, 0, 0);
  HAL_NVIC_EnableIRQ(EXTI3_IRQn);

  HAL_NVIC_SetPriority(EXTI15_10_IRQn, 0, 0);
  HAL_NVIC_EnableIRQ(EXTI15_10_IRQn);

  /* USER CODE BEGIN MX_GPIO_Init_2 */

  /* USER CODE END MX_GPIO_Init_2 */
}

/* USER CODE BEGIN 4 */
void OnTxDone( void )
{
    Radio.Sleep( );
    State = TX;
}

void OnRxDone( uint8_t *payload, uint16_t size, int16_t rssi, int8_t snr )
{
    Radio.Sleep( );
    BufferSize = size;
    memcpy( Buffer, payload, BufferSize );
    RssiValue = rssi;
    SnrValue = snr;
    State = RX;

    if (Buffer[0] == Rx_ID)
	{
    	if(strcmp((char*)Buffer + 1, "DONE") == 0){
    		lora_ok_flag = 1;
    	}
	}
}

void OnTxTimeout( void )
{
    Radio.Sleep( );
    State = TX;
    printf( "> OnTxTimeout\n");
}

void OnRxTimeout( void )
{
    Radio.Sleep( );
    Buffer[BufferSize] = 0;
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
