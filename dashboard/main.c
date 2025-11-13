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
#include <stdlib.h>
/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */

/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */
#define RF_FREQUENCY        922100000 // Hz
#define TX_OUTPUT_POWER     14        // dBm

#define LORA_BANDWIDTH      0         // 0: 125 kHz
#define LORA_SPREADING_FACTOR 7       // SF7
#define LORA_CODINGRATE     1         // 4/5

#define LORA_PREAMBLE_LENGTH 8
#define LORA_SYMBOL_TIMEOUT  0
#define LORA_FIX_LENGTH_PAYLOAD_ON false
#define LORA_IQ_INVERSION_ON false

#define RX_TIMEOUT_VALUE    1000
#define BUFFER_SIZE         64

#define Rx_ID               20
#define PHYMAC_PDUOFFSET_RXID 0

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/
TIM_HandleTypeDef htim2;

UART_HandleTypeDef huart2;

// motor move valuable
int current_angle = 0;
int Lavender_angle = 0;
int Cedarwood_angle = 90;
int Vanilla_angle = 180;
int Bergamot_angle = 270;
int move_angle = 0;

// lora valuable
uint16_t BufferSize = BUFFER_SIZE;
uint8_t Buffer[BUFFER_SIZE];

int8_t RssiValue = 0;
int8_t SnrValue = 0;

static RadioEvents_t RadioEvents;

volatile uint8_t lora_ok_flag = 0; // check OK message
volatile uint8_t lora_wait_flag = 0; // check wait

typedef enum {
    LOWPOWER = 0,
    IDLE,
    RX,
    RX_TIMEOUT,
    RX_ERROR,
    TX,
    TX_TIMEOUT
} States_t;

volatile States_t State = RX;

/* USER CODE BEGIN PV */

/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_USART2_UART_Init(void);
static void MX_TIM2_Init(void);

// lora function prototype
void OnTxDone( void );
void OnRxDone( uint8_t *payload, uint16_t size, int16_t rssi, int8_t snr );
void OnTxTimeout( void );
void OnRxTimeout( void );
void OnRxError( void );

/* USER CODE BEGIN PFP */
// Define the GPIO pins connected to IN1, IN2, IN3, IN4(Step motor)
#define IN1_PORT GPIOA
#define IN1_PIN  GPIO_PIN_5
#define IN2_PORT GPIOA
#define IN2_PIN  GPIO_PIN_6
#define IN3_PORT GPIOA
#define IN3_PIN  GPIO_PIN_7
#define IN4_PORT GPIOB
#define IN4_PIN  GPIO_PIN_6

// limit switch
#define LIMIT_SWITCH_PORT GPIOA
#define LIMIT_SWITCH_PIN  GPIO_PIN_0

int __io_putchar(int ch) {
	HAL_UART_Transmit(&huart2, (uint8_t*)&ch, 1, HAL_MAX_DELAY);
	return ch;
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
/*
void ResetMotor(){
	while(HAL_GPIO_ReadPin(LIMIT_SWITCH_PORT, LIMIT_SWITCH_PIN)){
		MoveMotorSteps(-1, 3);
	}
	MoveMotorSteps(5, 3);

	SetMotorPins(
			half_step_sequence[0][0],
	        half_step_sequence[0][1],
	        half_step_sequence[0][2],
	        half_step_sequence[0][3]);

	current_angle = 0;

	// 완료 통신할 것인지?
}
*/

void OnTxDone(void)
{
    Radio.Sleep();
    State = RX;  // 자동으로 RX 모드 진입
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


// wait OK message
void WaitForLoRaOK_Blocking()
{
    lora_ok_flag = 0;
    lora_wait_flag = 1;

    // LoRa 수신 시작
    State = RX;

    // OK가 들어올 때까지 Blocking
    while (lora_ok_flag == 0)
    {
        // State machine 유지
        switch (State)
        {
            case RX:
                Radio.Rx(RX_TIMEOUT_VALUE);
                State = IDLE;
                break;

            case TX:
                HAL_Delay(100);
                State = IDLE;
                break;
        }

        HAL_Delay(5);
    }

    // OK 받음 -> 종료
    lora_wait_flag = 0;
}

void OnRxDone( uint8_t *payload, uint16_t size, int16_t rssi, int8_t snr )
{
    uint8_t dataIndFlag = 0;

    Radio.Sleep();
    BufferSize = size;
    memcpy(Buffer, payload, BufferSize);
    RssiValue = rssi;
    SnrValue = snr;
    State = RX;

    if (Buffer[PHYMAC_PDUOFFSET_RXID] == Rx_ID) {
        dataIndFlag = 1;
    }

    if (dataIndFlag){
        printf("pong: ");
        for (int i = 1; i < BufferSize; i++) {
            printf("%c", payload[i]);
        }
        printf("\n\r");
    }

    // ✔ OK 메시지 감지
    if (strstr((char *)(payload + 1), "OK") != NULL) {
        lora_ok_flag = 1;  // OK 수신
    }
}






// home(angle = 0)
void LavenderMove(){
	move_angle = Lavender_angle - current_angle;
	if(move_angle > 180) move_angle -= 360;
	if(move_angle < -180) move_angle += 360;

	MoveMotorSteps(1024*move_angle/90, 2);
	current_angle = (current_angle + move_angle + 360) % 360;

	// Send a ready message
	Buffer[0] = Rx_ID;
	strcpy((char*)Buffer + 1, "LAVENDER_READY");
	Radio.Send(Buffer, BufferSize);

	// wait ok msseage
	WaitForLoRaOK_Blocking();
}

void CedarwoodMove(){
	move_angle = Cedarwood_angle - current_angle;
	if(move_angle > 180) move_angle -= 360;
	if(move_angle < -180) move_angle += 360;
	MoveMotorSteps(1024*move_angle/90, 2);
	current_angle = (current_angle + move_angle + 360) % 360;

	// Send a ready message
	Buffer[0] = Rx_ID;
	strcpy((char*)Buffer + 1, "CEDARWOOD_READY");
	Radio.Send(Buffer, BufferSize);

	// wait ok msseage
	WaitForLoRaOK_Blocking();
}

void VanillaMove(){
	move_angle = Vanilla_angle - current_angle;
	if(move_angle > 180) move_angle -= 360;
	if(move_angle < -180) move_angle += 360;
	MoveMotorSteps(1024*move_angle/90, 2);
	current_angle = (current_angle + move_angle + 360) % 360;

	// Send a ready message
	Buffer[0] = Rx_ID;
	strcpy((char*)Buffer + 1, "VANILLA_READY");
	Radio.Send(Buffer, BufferSize);

	// wait ok msseage
	WaitForLoRaOK_Blocking();
}

void BergamotMove(){
	move_angle = Bergamot_angle - current_angle;
	if(move_angle > 180) move_angle -= 360;
	if(move_angle < -180) move_angle += 360;
	MoveMotorSteps(1024*move_angle/90, 2);
	current_angle = (current_angle + move_angle + 360) % 360;

	// Send a ready message
	Buffer[0] = Rx_ID;
	strcpy((char*)Buffer + 1, "BERGAMOT_READY");
	Radio.Send(Buffer, BufferSize);

	// wait ok msseage
	WaitForLoRaOK_Blocking();
}








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
  void StepMotor_HalfStep(void);
  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER CODE BEGIN SysInit */

  /* USER CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  MX_USART2_UART_Init();
  MX_TIM2_Init();
  // ResetMotor();
  /* USER CODE BEGIN 2 */
  int menu = 1;
  // LoRa RadioEvents callback 연결
  RadioEvents.TxDone    = OnTxDone;
  RadioEvents.RxDone    = OnRxDone;
  RadioEvents.TxTimeout = OnTxTimeout;
  RadioEvents.RxTimeout = OnRxTimeout;
  RadioEvents.RxError   = OnRxError;

  Radio.Init(&RadioEvents);

  // 주파수 설정
  Radio.SetChannel(RF_FREQUENCY);

  // 송신/수신 설정
  Radio.SetTxConfig(
      MODEM_LORA,
      TX_OUTPUT_POWER,
      0,
      LORA_BANDWIDTH,
      LORA_SPREADING_FACTOR,
      LORA_CODINGRATE,
      LORA_PREAMBLE_LENGTH,
      LORA_FIX_LENGTH_PAYLOAD_ON,
      true,
      0,
      0,
      LORA_IQ_INVERSION_ON,
      3000
  );

  Radio.SetRxConfig(
      MODEM_LORA,
      LORA_BANDWIDTH,
      LORA_SPREADING_FACTOR,
      LORA_CODINGRATE,
      0,
      LORA_PREAMBLE_LENGTH,
      LORA_SYMBOL_TIMEOUT,
      LORA_FIX_LENGTH_PAYLOAD_ON,
      0,
      true,
      0,
      0,
      LORA_IQ_INVERSION_ON,
      true
  );

  // 패킷 첫 바이트에 ID 넣어두기
  Buffer[0] = Rx_ID;


  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {
	  // menu 터치패드로 신호를 받음
	  switch(menu){
	  	  case 1: // fresh
	  		  LavenderMove();
	  		  CedarwoodMove();
	  		  VanillaMove();
	  		  BergamotMove();
	  		  menu = 0;
	  		  break;
	  	  case 2: // calm
	  		  LavenderMove();
	  		  CedarwoodMove();
	   		  VanillaMove();
	   		  BergamotMove();
	   		  menu = 0;
	   		  break;
	  	  case 3: // confident
	  		  LavenderMove();
	  		  CedarwoodMove();
	  		  VanillaMove();
	  		  BergamotMove();
	  		  menu = 0;
	  		  break;
	  	  case 4: // sweet & romantic
	  		  LavenderMove();
	  		  CedarwoodMove();
	  		  VanillaMove();
	  		  BergamotMove();
	  		  menu = 0;
	  		  break;
	  	  case 5: // energetic
	  		  LavenderMove();
	  		  CedarwoodMove();
	  		  VanillaMove();
	  		  BergamotMove();
	  		  menu = 0;
	  		  break;
	  	  case 6: // cozy
	  		  LavenderMove();
	  		  CedarwoodMove();
	  		  VanillaMove();
	  		  BergamotMove();
	  		  menu = 0;
	  		  break;
	  	  case 7: // deep & mystic
	  		  LavenderMove();
	  		  CedarwoodMove();
	  		  VanillaMove();
	  		  BergamotMove();
	  		  menu = 0;
	  		  break;




	  }



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
  htim2.Init.Prescaler = 4999;
  htim2.Init.CounterMode = TIM_COUNTERMODE_UP;
  htim2.Init.Period = 4999;
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
  GPIO_InitStruct.Pin = GPIO_PIN_5 | GPIO_PIN_6 | GPIO_PIN_7;
    GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
    GPIO_InitStruct.Pull = GPIO_NOPULL;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);

    GPIO_InitStruct.Pin = GPIO_PIN_6;
    HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);
  /* USER CODE END MX_GPIO_Init_1 */

  /* GPIO Ports Clock Enable */
  __HAL_RCC_GPIOC_CLK_ENABLE();
  __HAL_RCC_GPIOH_CLK_ENABLE();
  __HAL_RCC_GPIOA_CLK_ENABLE();
  __HAL_RCC_GPIOB_CLK_ENABLE();

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(GPIOA, GPIO_PIN_5|GPIO_PIN_6|GPIO_PIN_7, GPIO_PIN_RESET);

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(GPIOB, GPIO_PIN_6, GPIO_PIN_RESET);

  /*Configure GPIO pin : B1_Pin */
  GPIO_InitStruct.Pin = B1_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_IT_FALLING;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  HAL_GPIO_Init(B1_GPIO_Port, &GPIO_InitStruct);

  /*Configure GPIO pin : PA0 */
  GPIO_InitStruct.Pin = GPIO_PIN_0;
  GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
  GPIO_InitStruct.Pull = GPIO_PULLUP;
  HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);

  /*Configure GPIO pins : PA5 PA6 PA7 */
  GPIO_InitStruct.Pin = GPIO_PIN_5|GPIO_PIN_6|GPIO_PIN_7;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);

  /*Configure GPIO pin : PB6 */
  GPIO_InitStruct.Pin = GPIO_PIN_6;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);

  /* EXTI interrupt init*/
  HAL_NVIC_SetPriority(EXTI15_10_IRQn, 0, 0);
  HAL_NVIC_EnableIRQ(EXTI15_10_IRQn);

  /* USER CODE BEGIN MX_GPIO_Init_2 */

  /* USER CODE END MX_GPIO_Init_2 */
}

/* USER CODE BEGIN 4 */

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
