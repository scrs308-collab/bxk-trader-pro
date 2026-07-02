async function loadDashboard() {

    const response = await fetch("/recommend");
    const data = await response.json();

    let strategyHTML = "";

    data.strategies.forEach((s, i) => {

        strategyHTML += `
            <tr>
                <td>${i + 1}</td>
                <td>${s.name}</td>
                <td>${s.score}</td>
                <td>${s.confidence}</td>
            </tr>
        `;

    });

    document.getElementById("dashboard").innerHTML = `

    <div class="card">

        <h1>BXK Trader Pro</h1>

        <h2>${data.trade}</h2>

        <p><b>Recommendation:</b> ${data.recommendation}</p>

        <p><b>Confidence:</b> ${data.confidence}%</p>

        <p><b>Score:</b> ${data.score}</p>

        <p><b>Trend:</b> ${data.trend}</p>

        <p><b>VIX:</b> ${data.vix_state}</p>

        <p><b>Expected Move:</b> ${data.expected_move_state}</p>

        <p><b>IV Rank:</b> ${data.iv_rank_state}</p>

    </div>

    <div class="card">

        <h2>Top Strategies Today</h2>

        <table>

            <tr>
                <th>#</th>
                <th>Strategy</th>
                <th>Score</th>
                <th>Confidence</th>
            </tr>

            ${strategyHTML}

        </table>

    </div>

    <div class="card">

        <h2>Decision Reasons</h2>

        <ul>

            ${data.reasons.map(r => `<li>${r}</li>`).join("")}

        </ul>

    </div>

    `;

}

loadDashboard();