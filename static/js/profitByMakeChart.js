document.addEventListener('DOMContentLoaded', function () {
    var canvas = document.getElementById('profitChart');
    if (!canvas) return;
    console.log('Ready for fake bars');

    var makes = ['Toyota', 'Ford'];
    var profits = [10000, 5000];
    var colors = ['blue', 'orange'];

    var ctx = canvas.getContext('2d');
    new Chart(ctx, {
        type: 'bar'
        data: {
            labels: makes,
            datasets: [{
                data: profits,
                backgroundColor: colors
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: { beginAtZero: true }
            }
        }
    });
    console.log('Fake bars drawn!');
});