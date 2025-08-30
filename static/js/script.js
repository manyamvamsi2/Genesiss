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
        
        // Show loading, hide results and error
        loadingElement.style.display = 'block';
        resultsElement.style.display = 'none';
        errorElement.style.display = 'none';
        
        // Create FormData object
        const formData = new FormData(form);
        
        // Add X-Requested-With header for AJAX detection
        const headers = {
            'X-Requested-With': 'XMLHttpRequest'
        };
        
        // Send AJAX request
        fetch('/generate', {
            method: 'POST',
            body: formData,
            headers: headers
        })
        .then(response => {
            // First, check if response is OK (status 200-299)
            if (!response.ok) {
                // Try to parse as JSON, but fall back to text if it fails
                return response.text().then(text => {
                    try {
                        const errorData = JSON.parse(text);
                        throw new Error(errorData.error || `Server error: ${response.status}`);
                    } catch (e) {
                        throw new Error(`Server error: ${response.status} - ${text}`);
                    }
                });
            }
            return response.json();
        })
        .then(data => {
            loadingElement.style.display = 'none';
            
            if (data.error) {
                errorElement.textContent = data.error;
                errorElement.style.display = 'block';
                return;
            }
            
            // Display results
            displayResults(data);
            resultsElement.style.display = 'block';
            
            // Smooth scroll to results
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
        // Safely update metrics with default values
        const analysis = data.analysis || {};
        
        document.getElementById('total-transactions').textContent = 
            (analysis.total_transactions || 0).toLocaleString();
        
        document.getElementById('fraudulent-transactions').textContent = 
            (analysis.fraud_count || 0).toLocaleString();
        
        document.getElementById('total-amount').textContent = 
            '$' + (analysis.total_amount || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
        
        document.getElementById('avg-transaction').textContent = 
            '$' + (analysis.avg_transaction || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
        
        // Create transaction type distribution chart
        if (data.category_distribution && data.category_distribution.length > 0) {
            createPieChart('category-distribution-chart', 'Transaction Type Distribution', data.category_distribution);
        } else {
            document.getElementById('category-distribution-chart').innerHTML = 
                '<p>No category distribution data available.</p>';
        }
        
        // Create fraud by category chart
        if (data.fraud_by_category && data.fraud_by_category.length > 0) {
            createBarChart('fraud-by-category-chart', 'Fraudulent Transactions by Type', data.fraud_by_category);
        } else {
            document.getElementById('fraud-by-category-chart').innerHTML = 
                '<p>No fraud analysis data available.</p>';
        }
        
        // Update risk patterns
        const riskPatternsContainer = document.getElementById('risk-patterns');
        riskPatternsContainer.innerHTML = '';
        
        if (analysis.risk_patterns && Object.keys(analysis.risk_patterns).length > 0) {
            for (const [pattern, count] of Object.entries(analysis.risk_patterns)) {
                const patternElement = document.createElement('div');
                patternElement.className = 'risk-pattern';
                
                const patternName = pattern.split('_').map(word => {
                    // Handle special cases
                    if (word.toLowerCase() === 'micro') return 'Micro';
                    if (word.toLowerCase() === 'large') return 'Large';
                    if (word.toLowerCase() === 'international') return 'International';
                    if (word.toLowerCase() === 'unusual') return 'Unusual';
                    if (word.toLowerCase() === 'merchant') return 'Merchant';
                    if (word.toLowerCase() === 'patterns') return 'Patterns';
                    if (word.toLowerCase() === 'transactions') return 'Transactions';
                    return word.charAt(0).toUpperCase() + word.slice(1);
                }).join(' ');
                
                patternElement.innerHTML = `
                    <span>${patternName}</span>
                    <span class="risk-count">${count || 0}</span>
                `;
                
                riskPatternsContainer.appendChild(patternElement);
            }
        } else {
            riskPatternsContainer.innerHTML = '<p>No risk patterns detected.</p>';
        }
        
        // Update sample transactions table
        const sampleTable = document.getElementById('sample-transactions');
        const tbody = sampleTable.querySelector('tbody');
        tbody.innerHTML = '';
        
        if (data.sample_data && data.sample_data.length > 0) {
            data.sample_data.forEach(row => {
                const tr = document.createElement('tr');
                
                // Format the data for display with safe defaults
                const id = row.transaction_id || row.id || 'T' + Math.random().toString(36).substr(2, 6).toUpperCase();
                const date = row.transaction_date || row.date || new Date().toISOString().split('T')[0];
                const amount = row.amount ? '$' + parseFloat(row.amount).toFixed(2) : '$0.00';
                const type = row.merchant_category || row.type || 'Unknown';
                const merchant = formatMerchantName(type);
                const location = row.location || 'Unknown';
                const status = row.is_fraud === 1 ? 'Fraudulent' : 'Normal';
                
                tr.innerHTML = `
                    <td>${id}</td>
                    <td>${date}</td>
                    <td>${amount}</td>
                    <td>${type}</td>
                    <td>${merchant}</td>
                    <td>${location}</td>
                    <td>${status}</td>
                `;
                
                tbody.appendChild(tr);
            });
        } else {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align: center;">No sample data available.</td></tr>';
        }
        
        // Store data for download
        window.syntheticData = data.sample_data || [];
    }
    
    function formatMerchantName(type) {
        const merchants = {
            'retail': 'Department Store',
            'online': 'Online Marketplace',
            'grocery': 'Grocery Store',
            'food': 'Restaurant',
            'travel': 'Travel Agency',
            'entertainment': 'Entertainment Venue',
            'services': 'Service Provider',
            'utilities': 'Utility Company',
            'healthcare': 'Healthcare Provider',
            'education': 'Educational Institution',
            'unknown': 'Unknown Merchant'
        };
        
        return merchants[type.toLowerCase()] || type;
    }
    
    function createPieChart(containerId, title, data) {
        const container = document.getElementById(containerId);
        container.innerHTML = '';
        
        if (!data || data.length === 0) return;
        
        // Create title
        const titleElement = document.createElement('h3');
        titleElement.textContent = title;
        titleElement.style.marginBottom = '15px';
        titleElement.style.color = 'var(--primary-color)';
        container.appendChild(titleElement);
        
        // Create legend
        const legendContainer = document.createElement('div');
        legendContainer.className = 'pie-chart-legend';
        
        data.forEach(item => {
            const legendItem = document.createElement('div');
            legendItem.className = 'pie-legend-item';
            
            const colorBox = document.createElement('div');
            colorBox.className = 'pie-color';
            colorBox.style.backgroundColor = getRandomColor();
            
            const label = document.createElement('span');
            label.textContent = `${item.category}: ${item.count || 0}`;
            
            legendItem.appendChild(colorBox);
            legendItem.appendChild(label);
            legendContainer.appendChild(legendItem);
        });
        
        container.appendChild(legendContainer);
    }
    
    function createBarChart(containerId, title, data) {
        const container = document.getElementById(containerId);
        container.innerHTML = '';
        
        if (!data || data.length === 0) return;
        
        // Create title
        const titleElement = document.createElement('h3');
        titleElement.textContent = title;
        titleElement.style.marginBottom = '15px';
        titleElement.style.color = 'var(--primary-color)';
        container.appendChild(titleElement);
        
        // Find max value for scaling
        const maxValue = Math.max(...data.map(item => item.count || 0));
        
        // Create bars
        data.forEach(item => {
            const barContainer = document.createElement('div');
            barContainer.className = 'chart-bar';
            
            const label = document.createElement('div');
            label.className = 'chart-label';
            label.textContent = item.category;
            
            const valueBar = document.createElement('div');
            valueBar.className = 'chart-value';
            valueBar.style.width = `${((item.count || 0) / maxValue) * 100}%`;
            valueBar.textContent = item.count || 0;
            
            barContainer.appendChild(label);
            barContainer.appendChild(valueBar);
            container.appendChild(barContainer);
        });
    }
    
    function getRandomColor() {
        const colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', 
                       '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'];
        return colors[Math.floor(Math.random() * colors.length)];
    }
    
    // Download functionality
    document.getElementById('download-csv').addEventListener('click', function() {
        downloadData('csv');
    });
    
    document.getElementById('download-json').addEventListener('click', function() {
        downloadData('json');
    });
    
    function downloadData(format) {
        // Simple GET request to the download endpoint
        window.open(`/download/${format}`, '_blank');
    }
});

// Global function for updating slider values
function updateValue(sliderId, valueId) {
    const slider = document.getElementById(sliderId);
    const valueDisplay = document.getElementById(valueId);
    
    if (sliderId === 'fraud_percentage') {
        valueDisplay.textContent = slider.value + '%';
    } else {
        valueDisplay.textContent = slider.value;
    }
}