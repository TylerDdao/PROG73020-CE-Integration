CREATE TABLE IF NOT EXISTS restock_requests (
    request_id INT AUTO_INCREMENT PRIMARY KEY,
    vendor_id VARCHAR(255),
    status VARCHAR(255) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS restock_requests_manifests (
    manifest_id INT AUTO_INCREMENT PRIMARY KEY,
    request_id INT NOT NULL,
    FOREIGN KEY (request_id) REFERENCES restock_requests(request_id),
    product_id VARCHAR(255) NOT NULL,
    quantity_order INT NOT NULL
);

CREATE TABLE IF NOT EXISTS stock_events (
    stock_event_id INT AUTO_INCREMENT PRIMARY KEY,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS stock_events_products(
    stock_events_products_id INT AUTO_INCREMENT PRIMARY KEY,
    stock_event_id INT,
    FOREIGN KEY (stock_event_id) REFERENCES stock_events(stock_event_id),
    product_id VARCHAR(255),
    quantity_change INT,
    unit VARCHAR(2)
);

-- Stock events
INSERT INTO stock_events (status) VALUES ('pending');
INSERT INTO stock_events (status) VALUES ('pending');
INSERT INTO stock_events (status) VALUES ('pending');

-- Stock event products
INSERT INTO stock_events_products (stock_event_id, product_id, quantity_change, unit) VALUES (1, 'PROD-BEEF-GROUND', -100, 'kg');
INSERT INTO stock_events_products (stock_event_id, product_id, quantity_change, unit) VALUES (2, 'PROD-BEEF-STEAK', -5, 'kg');
INSERT INTO stock_events_products (stock_event_id, product_id, quantity_change, unit) VALUES (3, 'WF-CARROTS', -8, 'kg');
INSERT INTO stock_events_products (stock_event_id, product_id, quantity_change, unit) VALUES (3, 'WF-APPLES', -3, 'kg');
INSERT INTO stock_events_products (stock_event_id, product_id, quantity_change, unit) VALUES (3, 'PROD-BUTTER', -2, 'kg');

-- Restock requests
INSERT INTO restock_requests (vendor_id, status) VALUES ('VENDOR-001', 'pending');
INSERT INTO restock_requests (vendor_id, status) VALUES ('VENDOR-002', 'approved');

-- Restock request manifests
INSERT INTO restock_requests_manifests (request_id, product_id, quantity_order) VALUES (1, 'PROD-MILK', 50);
INSERT INTO restock_requests_manifests (request_id, product_id, quantity_order) VALUES (1, 'PROD-JUICE', 30);
INSERT INTO restock_requests_manifests (request_id, product_id, quantity_order) VALUES (2, 'WF-CARROTS', 100);
INSERT INTO restock_requests_manifests (request_id, product_id, quantity_order) VALUES (2, 'WF-APPLES', 75);