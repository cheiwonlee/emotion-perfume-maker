'use strict';

document.addEventListener('DOMContentLoaded', () => {

    const SCENT_NAMES = ["Lavender", "Cedarwood", "Vanilla", "Bergamot"];
    const updateInterval = 2000; // 2초마다 갱신

    /**
     * Django 템플릿 변수를 JavaScript 객체로 안전하게 추출합니다.
     * Django는 쿼리셋의 값을 {{ list.0.value }} 형태로 템플릿에 직접 렌더링하므로, 
     * 여기서는 페이지를 새로고침하는 방식으로 데이터를 갱신합니다.
     * * ⚠️ 중요: 이 HTML 구조에서는 데이터 갱신을 위해 전체 페이지를 새로고침하는 것이 
     * 가장 간단하고 안전한 방법입니다. 만약 비동기 갱신을 원한다면, 
     * 모든 센서 카드와 메인 상태 카드의 HTML 요소를 동적으로 업데이트하는 로직이 필요하며, 
     * 이는 이 파일의 범위를 넘어섭니다.
     * * 현재 구조에서는 2초마다 전체 페이지를 새로고침합니다.
     */
    
    function refreshPage() {
        console.log("2초마다 페이지 전체를 새로고침합니다.");
        window.location.reload(true);
    }
    
    // 이 코드는 HTML에서 <meta http-equiv="refresh" content="1">를 제거했기 때문에,
    // 2초마다 페이지를 새로고침하여 최신 DB 데이터를 가져옵니다.
    // setInterval(refreshPage, updateInterval); 
    
    // 하지만, 페이지 깜빡임을 방지하고 효율성을 높이기 위해 
    // `getStatus`를 사용한 비동기 업데이트 로직을 구현합니다.

    // ----------------------------------------------------------------------
    // 비동기 업데이트 로직 (권장)
    // ----------------------------------------------------------------------

    // HTML 요소의 텍스트와 클래스를 갱신하는 함수
    function updateSensorCard(name, isBad, timestamp) {
        const card = document.querySelector(`.card.sensor-card:nth-child(${SCENT_NAMES.indexOf(name) + 2})`);
        if (!card) return;

        card.classList.remove('sensor-ok', 'sensor-bad');
        card.classList.add(isBad ? 'sensor-bad' : 'sensor-ok');

        const statusText = card.querySelector('.sensor-status-text');
        const detailText = card.querySelector('div:nth-child(4)'); 
        const timeElement = card.querySelector('.timestamp');

        if (statusText) {
            statusText.classList.remove('text-ok', 'text-bad');
            statusText.classList.add(isBad ? 'text-bad' : 'text-ok');
            statusText.textContent = isBad ? '부족 (Empty)' : '정상 (Full)';
        }
        if (detailText) {
             detailText.textContent = isBad ? '보충이 필요합니다' : '제조 가능';
        }
        if (timeElement) {
            const dateObj = new Date(timestamp);
            const timeString = dateObj.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
            timeElement.textContent = timeString;
        }
    }
    
    // 메인 상태 카드 (Status 모델) 및 경고 배너 갱신
    function updateMainStatus(statusData, proxData) {
        const statusCard = document.querySelector('.status-card');
        const alertBanner = document.querySelector('.system-alert');
        if (!statusCard) return;

        const { ui_state, mood_name, recipe_L, recipe_C, recipe_V, recipe_B, reg_date } = statusData;
        
        // 1. 메인 컨트롤러 상태 업데이트
        const moodNameElement = statusCard.querySelector('.mood-name');
        const processTextElement = statusCard.querySelector('.current-mood div:last-child');
        const timestampElement = statusCard.querySelector('.status-card .timestamp');
        
        if (moodNameElement) moodNameElement.textContent = mood_name || 'Ready';
        if (timestampElement && reg_date) {
            const dateObj = new Date(reg_date);
            const timeString = dateObj.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
            timestampElement.textContent = `Last Update: ${timeString}`;
        }
        
        if (processTextElement) {
            let text = '';
            let color = '#999';
            let icon = 'fas fa-pause-circle';

            if (ui_state === 'START') {
                text = '대기 중 (Idle)';
            } else if (ui_state.startsWith('BLENDING')) {
                text = '제조 진행 중...';
                color = 'var(--warning)';
                icon = 'fas fa-sync fa-spin';
            } else if (ui_state === 'FINISH') {
                text = '제조 완료!';
                color = 'var(--success)';
                icon = 'fas fa-check-circle';
            } else {
                text = ui_state;
            }
            processTextElement.innerHTML = `<span style="color: ${color};"><i class="${icon}"></i> ${text}</span>`;
        }

        // 2. 프로세스 시각화 (모터 아이콘) 업데이트
        const motorStates = {
            'Lavender': recipe_L,
            'Cedarwood': recipe_C,
            'Vanilla': recipe_V,
            'Bergamot': recipe_B,
        };
        
        SCENT_NAMES.forEach(name => {
            const motorItem = statusCard.querySelector(`.motor-item:nth-child(${SCENT_NAMES.indexOf(name) + 1})`);
            if (motorItem) {
                const isActive = ui_state === `BLENDING_${name.charAt(0)}`;
                motorItem.classList.toggle('active', isActive);
                
                const motorValue = motorItem.querySelector('.motor-value');
                // Floatformat은 서버에서 처리해야 하지만, 혹시 모를 경우를 대비해 toFixed(1) 사용
                if (motorValue) motorValue.textContent = `${motorStates[name].toFixed(1)}ml`;
            }
        });

        // 3. 재고 부족 경고 배너 업데이트
        let missingItems = [];
        proxData.forEach(item => {
            // item.value가 True(부족)인 경우
            if (item.value) { 
                missingItems.push(item.name);
            }
            // 센서 카드 상태도 여기서 업데이트
            updateSensorCard(item.name, item.value, item.reg_date);
        });
        
        if (missingItems.length > 0) {
            // 경고 배너가 없으면 생성해야 하지만, 템플릿에 이미 조건부로 있으므로, 
            // 여기서는 경고 배너가 표시되도록 페이지를 새로고침하거나 DOM을 조작해야 합니다.
            // 가장 간단하게는 페이지 새로고침을 유도합니다.
            // 하지만 현재는 index.html이 Django 템플릿에서 모든 센서 목록을 받으므로, 
            // 이 경고 배너의 내용 자체는 서버에서만 결정됩니다.
            // 비동기로 하려면 alertBanner의 구조를 완전히 JS로 제어해야 합니다.
            // 여기서는 경고 배너를 무시하고 센서 카드만 업데이트합니다.
            console.warn("재고 부족 알림: ", missingItems.join(', '));
            
            // 만약 서버의 템플릿이 아닌, 클라이언트에서 경고 배너를 띄우고 싶다면:
            // if (!alertBanner) { window.location.reload(); }
        }
    }


    /**
     * 서버에서 최신 Status 데이터와 ProximitySensor 데이터를 비동기적으로 가져옵니다.
     * * ⚠️ ProximitySensor 데이터는 API가 아닌, Django 템플릿 변수에 의존하는 
     * HTML 구조 때문에 현재 `getProxByName`을 통해 가져와야 합니다.
     * 데이터 일관성을 위해 모든 센서의 최신 데이터를 한 번에 가져오는 새 API가 없다고 가정하고,
     * `getStatus`와 `getProxByName`을 조합합니다.
     */
    async function fetchAndUpdateData() {
        try {
            // 1. Status 데이터 가져오기 (메인 상태)
            const statusResponse = await fetch('/sensor/getStatus');
            const latestStatus = await statusResponse.json();

            // 2. ProximitySensor 데이터 가져오기 (4개 센서 상태)
            const proxData = [];
            for (const name of SCENT_NAMES) {
                const proxResponse = await fetch(`/sensor/getProxByName/${name}/1`);
                const latestProx = await proxResponse.json();
                if (latestProx.length > 0) {
                    proxData.push({
                        name: name,
                        value: latestProx[0].value,
                        reg_date: latestProx[0].reg_date
                    });
                }
            }
            
            // 3. UI 업데이트
            if (latestStatus) {
                updateMainStatus(latestStatus, proxData);
            }
            
        } catch (error) {
            console.error("데이터 갱신 오류:", error);
            // 오프라인 상태를 시각적으로 표시할 수 있습니다.
            const wifiIcons = document.querySelectorAll('.fa-wifi');
            wifiIcons.forEach(icon => icon.style.color = 'var(--danger)');
        }
    }

    // 2초마다 갱신 시작
    setInterval(fetchAndUpdateData, updateInterval); 
    
    // 페이지 로드 시 즉시 실행
    fetchAndUpdateData();
});