// profitByMakeChart.js - Minimal Test Version (No Emojis, Arrow-Free)
document.addEventListener('DOMContentLoaded', function () {
    var canvas = document.getElementById('profitChart');
    if (!canvas) {
        console.log('No canvas found');
        return;
    }
    console.log('Canvas ready');

    fetch('/api/inventory')
        .then(function (res) {
            if (!res.ok) {
                throw new Error('API failed: ' + res.status);
            }
            return res.json();
        })
        .then(function (response) {
            var data = response.formatted_data || [];
            console.log('Total cars: ' + data.length);

            data = data.filter(function (car) {
                return car.status === 'Sold';
            });
            console.log('Sold cars: ' + data.length);
            if (data.length === 0) {
                canvas.parentNode.innerHTML = '<p>No sold cars</p>';
                return;
            }

            var makeProfits = {};
            data.forEach(function (car) {
                var make = car.make || 'Unknown';
                var profitStr = car.profit || '';
                var cleanProfit = profitStr.replace(/UGX |[+$]/g, '').replace(/,/g, '');
                var profit = parseFloat(cleanProfit) || 0;
                if (!makeProfits[make]) {
                    makeProfits[make] = 0;
                }
                makeProfits[make] += profit;
            });
            console.log('Profits by make: ', makeProfits);

            var makes = Object.keys(makeProfits);
            var profits = Object.values(makeProfits);

            var sortedIndex = profits
                .map(function (profit, index) {
                    return { profit: profit, index: index };
                })
                .sort(function (a, b) {
                    return b.profit - a.profit;
                })
                .map(function (item) {
                    return item.index;
                });
            makes = sortedIndex.map(function (i) {
                return makes[i];
            });
            profits = sortedIndex.map(function (i) {
                return profits[i];
            });
            console.log('Sorted makes: ', makes);
            console.log('Sorted profits: ', profits);

            if (profits.length === 0 || profits.every(function (p) { return p === 0; })) {
                canvas.parentNode.innerHTML = '<p>No profits</p>';
                return;
            }

            var grandTotal = profits.reduce(function (sum, p) {
                return sum + p;
            }, 0);

            var supersetColors = [
                '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
                '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'
            ];
            var barColors = makes.map(function (_, i) {
                return supersetColors[i % supersetColors.length];
            });

            var ctx = canvas.getContext('2d');
            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: makes,
                    datasets: [{
                        label: 'Total Profit',
                        data: profits,
                        backgroundColor: barColors,
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'top',
                            labels: { usePointStyle: true }
                        },
                        tooltip: {
                            callbacks: {
                                title: function (context) {
                                    return context[0].label;
                                },
                                label: function (context) {
                                    var profit = context.parsed.y;
                                    var percent = ((profit / grandTotal) * 100).toFixed(1);
                                    return 'UGX ' + profit.toLocaleString() + ' (' + percent + '%)';
                                }
                            }
                        },
                        datalabels: {
                            anchor: 'end',
                            align: 'top',
                            formatter: function (value) {
                                return 'UGX ' + value.toLocaleString();
                            },
                            color: 'black',
                            font: { size: 12 }
                        }
                    },
                    scales: {
                        x: {
                            title: { display: true, text: 'Make', padding: { bottom: 30 } },
                            ticks: { maxRotation: 0 }
                        },
                        y: {
                            beginAtZero: true,
                            title: { display: true, text: 'Total Profit', position: 'left', padding: { right: 50 } },
                            ticks: {
                                callback: function (value) {
                                    return 'UGX ' + value.toLocaleString();
                                }
                            }
                        }
                    }
                }
            });
            console.log('Chart drawn!');
        })
        .catch(function (err) {
            console.error('Chart error: ', err);
            canvas.parentNode.innerHTML = '<p>Failed: ' + err.message + '</p>';
        });
});