'use strict';

$(document).ready(function () {

    var queryCnt = 100;

    // 향 목록
    var scents = [
        { name: "Lavender", chartId: "#chart_lavender" },
        { name: "Cedarwood", chartId: "#chart_cedarwood" },
        { name: "Vanilla", chartId: "#chart_vanilla" },
        { name: "Bergamot", chartId: "#chart_bergamot" }
    ];

    // 저장 공간
    var chartData = {
        "Lavender": [],
        "Cedarwood": [],
        "Vanilla": [],
        "Bergamot": []
    };

    // 공통 옵션
    var options = {
        colors: ["#4fb7fe"],
        series: {
            shadowSize: 0,
            lines: {
                show: true,
                fill: true,
                fillColor: {
                    colors: [{ opacity: 0.5 }, { opacity: 0.5 }]
                }
            }
        },
        yaxis: {
            min: -0.1,
            max: 1.1
        },
        xaxis: {
            show: false,
            min: 0,
            max: queryCnt
        },
        points: {
            show: true
        },
        grid: {
            backgroundColor: '#fff',
            borderWidth: 1,
            borderColor: '#fff',
            hoverable: true
        }
    };

    // 차트 초기화
    var plots = {};

    scents.forEach(s => {
        plots[s.name] = $.plot($(s.chartId), [[]], options);
    });

    function getDataFor(name) {

        // 기존 데이터 제거 (크기 유지)
        if (chartData[name].length > 0)
            chartData[name] = chartData[name].slice(1);

        $.ajax({
            url: "/sensor/getProxByName/" + name + "/" + queryCnt,
            type: "GET",
            dataType: "json",
            async: true,  // ✅ 비동기 처리 (UI 블로킹 방지)
            success: (res) => {
                chartData[name] = res;
            },
            error: (error) => {
                console.log(error);
            }
        });

        // flot 형태로 변환
        var formatted = [];
        for (var i = 0; i < chartData[name].length; ++i) {
            var y = chartData[name][i]["value"] ? 1 : 0;  // 🔥 boolean → number
            formatted.push([i, y]);
        }
        return formatted;

    }

    // 주기적으로 갱신
    function update() {

        scents.forEach(s => {
            plots[s.name].setData([getDataFor(s.name)]);
            plots[s.name].draw();
        });

        setTimeout(update, 500);  // ✅ 200ms → 500ms로 업데이트 간격 증가 (서버 부하 감소)
    }

    update();
});
