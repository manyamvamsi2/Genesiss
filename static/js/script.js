document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('simulation-form');
    const loadingElement = document.getElementById('loading');
    const resultsElement = document.getElementById('results');
    const errorElement = document.getElementById('error-message');
    
    // Initialize slider values
    updateValue('num_transactions', 'transactions-value');
    updateValue('fraud_percentage', 'fraud-value');
    
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        loadingElement.style.display = 'block';
        resultsElement.style.display = 'none';
        errorElement.style.display = 'none';
        
        const formData = new FormData(form);
        
        fetch('/generate', {
            method: 'POST',
            body: formData,
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => { throw new Error(err.error || `Server error: ${response.status}`) });
            }
            return response.json();
        })
        .then(data => {
            loadingElement.style.display = 'none';
            displayResults(data);
            resultsElement.style.display = 'block';
            resultsElement.scrollIntoView({ behavior: 'smooth' });
        })
        .catch(error => {
            loadingElement.style.display = 'none';
            errorElement.textContent = 'An error occurred: ' + error.message;
            errorElement.style.display = 'block';
            console.error('Error:', error);
        });
    });
    
    function displayResults(data) {
        // Safely update metrics
        const analysis = data.analysis || {};
        document.getElementById('total-transactions').textContent = (analysis.total_transactions || 0).toLocaleString();
        document.getElementById('fraudulent-transactions').textContent = (analysis.fraud_count || 0).toLocaleString();
        document.getElementById('total-amount').textContent = '$' + (analysis.total_amount || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
        document.getElementById('avg-transaction').textContent = '$' + (analysis.avg_transaction || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
        
        // Render the bar chart
        createBarChart('fraud-by-category-chart', data.fraud_by_category);
        
        // "Risk Patterns" population logic has been removed
        
        // Dynamically build the sample transactions table
        const sampleTable = document.getElementById('sample-transactions');
        const thead = sampleTable.querySelector('thead');
        const tbody = sampleTable.querySelector('tbody');
        thead.innerHTML = '';
        tbody.innerHTML = '';

        if (data.sample_data && data.sample_data.length > 0) {
            const headers = Object.keys(data.sample_data[0]);
            const headerRow = document.createElement('tr');
            headers.forEach(headerText => {
                const th = document.createElement('th');
                th.textContent = headerText.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                headerRow.appendChild(th);
            });
            thead.appendChild(headerRow);

            data.sample_data.forEach(rowData => {
                const tr = document.createElement('tr');
                headers.forEach(header => {
                    const td = document.createElement('td');
                    const cellValue = rowData[header];
                    td.textContent = (cellValue !== null && cellValue !== undefined) ? cellValue : 'N/A';
                    tr.appendChild(td);
                });
                tbody.appendChild(tr);
            });
        } else {
            thead.innerHTML = '<tr><th>No Sample Data Available</th></tr>';
        }
    }
    
    function createBarChart(containerId, data) {
        const container = document.getElementById(containerId);
        container.innerHTML = ''; // Clear previous chart
        if (!data || data.length === 0) {
            container.innerHTML = `<p class="no-data-message">No fraudulent transactions to analyze by category.</p>`;
            return;
        }

        const maxValue = Math.max(...data.map(item => item.count || 0));
        data.forEach(item => {
            const barContainer = document.createElement('div');
            barContainer.className = 'chart-bar';
            const percentage = maxValue > 0 ? ((item.count || 0) / maxValue) * 100 : 0;
            barContainer.innerHTML = `
                <div class="chart-label">${item.category}</div>
                <div class="chart-value" style="width: ${percentage}%;">${item.count.toLocaleString() || 0}</div>
            `;
            container.appendChild(barContainer);
        });
    }
    
    // Download functionality
    document.getElementById('download-csv').addEventListener('click', () => window.open('/download/csv', '_blank'));
    document.getElementById('download-json').addEventListener('click', () => window.open('/download/json', '_blank'));
});

// Global function for updating slider values
function updateValue(sliderId, valueId) {
    const slider = document.getElementById(sliderId);
    const valueDisplay = document.getElementById(valueId);
    
    if (sliderId === 'fraud_percentage') {
        valueDisplay.textContent = slider.value + '%';
    } else {
        valueDisplay.textContent = Number(slider.value).toLocaleString();
    }
}
