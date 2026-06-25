# Implementation Plan: Smart WiFi Dashboard

## Overview

This implementation plan breaks down the Smart WiFi Dashboard into incremental coding tasks following the architecture defined in the design document. The system uses Python FastAPI (backend), React.js with TypeScript and Tailwind CSS and Recharts (frontend), PostgreSQL with RLS (database), Redis (cache/pub-sub), Scikit-learn (AI), and Celery (task queue). Tasks are ordered to build foundational infrastructure first, then layer features with proper dependency management.

## Tasks

- [ ] 1. Project setup and infrastructure
  - [ ] 1.1 Initialize backend project structure with FastAPI
    - Create Python project with FastAPI, uvicorn, SQLAlchemy, alembic, pydantic, redis, celery dependencies
    - Set up directory structure: `backend/app/{api,services,models,schemas,core,tasks,tests}`
    - Create `main.py` with FastAPI app factory, CORS middleware, and router registration
    - Create `core/config.py` with Pydantic Settings for environment variables (DB URL, Redis URL, secret key)
    - _Requirements: 13.8_

  - [ ] 1.2 Initialize frontend project structure with React and Tailwind
    - Create React project with TypeScript, Tailwind CSS, React Router, Recharts, Axios
    - Set up directory structure: `frontend/src/{components,pages,hooks,services,context,types}`
    - Configure Tailwind with dark theme colors (dark blue/gray palette)
    - Create base layout component with sidebar navigation and top header
    - _Requirements: 11.1, 11.3, 11.4_

  - [ ] 1.3 Set up PostgreSQL database schema and migrations
    - Create Alembic migration configuration
    - Create SQLAlchemy models for all entities: Tenant, Admin, Device, BlockingScenario, FirewallRule, BandwidthConfig, QueueRule, TrafficData, AnomalyAlert, DeviceSession, Report, AuditLog, LoginAttempt, RouterConfig
    - Add tenant_id foreign keys and indexes on all tenant-scoped tables
    - Create initial migration with all tables, constraints, and indexes
    - Add monthly partitioning for traffic_data table on collected_at
    - _Requirements: 2.1, 2.4_

  - [ ] 1.4 Configure PostgreSQL Row-Level Security policies
    - Create RLS policies on all tenant-scoped tables enforcing tenant_id filtering
    - Create database role for application with RLS enforcement
    - Create helper function to set current tenant context via session variable
    - Write migration to enable RLS on all relevant tables
    - _Requirements: 2.2, 2.3, 2.4_

  - [ ] 1.5 Set up Redis connection and configuration
    - Create Redis client wrapper with connection pooling
    - Configure Redis for sessions, caching (10s TTL), and pub/sub channels
    - Create cache utility functions (get/set/invalidate with tenant-scoped keys)
    - _Requirements: 13.6, 13.7_

  - [ ] 1.6 Set up Celery task queue with Redis broker
    - Configure Celery app with Redis as broker and result backend
    - Create base task class with error handling and retry logic
    - Set up task routing for report generation and AI analysis workers
    - _Requirements: 8.5_

- [ ] 2. Authentication and multi-tenant isolation
  - [ ] 2.1 Implement authentication service with JWT
    - Create `services/auth_service.py` with login, logout, session validation
    - Implement bcrypt password hashing (cost factor 12) and verification
    - Implement JWT token generation with 30-minute sliding expiry
    - Create login endpoint `POST /api/auth/login` returning JWT token
    - Create logout endpoint `POST /api/auth/logout` invalidating token
    - Create session validation endpoint `GET /api/auth/session`
    - Implement input validation: username max 64 chars, password max 128 chars
    - Return identical error response for all invalid credential combinations (wrong username, wrong password, or both)
    - _Requirements: 1.2, 1.3, 1.8_

  - [ ]* 2.2 Write property tests for authentication
    - **Property 1: Authentication error message uniformity**
    - **Property 2: Session token expiry correctness**
    - **Property 4: Input length boundary validation**
    - **Validates: Requirements 1.3, 1.5, 1.8**

  - [ ] 2.3 Implement rate limiting and brute-force protection
    - Create Redis-backed sliding window rate limiter
    - Implement per-IP tracking: 5 failed attempts per 10-minute window → reject
    - Implement brute-force detection: 20 failed attempts per hour → 30-minute IP ban
    - Store login attempts in LoginAttempt table for audit
    - _Requirements: 1.6, 1.7_

  - [ ]* 2.4 Write property test for rate limiting
    - **Property 3: Sliding window rate limiting**
    - **Validates: Requirements 1.6, 1.7**

  - [ ] 2.5 Implement tenant isolation middleware
    - Create FastAPI middleware that extracts tenant_id from JWT token
    - Inject tenant_id into database session context for RLS enforcement
    - Create dependency injection for tenant-scoped database sessions
    - Implement cross-tenant access detection and logging
    - Return identical access-denied error without revealing target resource existence
    - _Requirements: 2.2, 2.3, 2.4, 2.5_

  - [ ]* 2.6 Write property tests for tenant isolation
    - **Property 5: Tenant data isolation**
    - **Property 6: Cross-tenant access rejection uniformity**
    - **Validates: Requirements 2.2, 2.3, 2.4**

  - [ ] 2.7 Implement frontend login page
    - Create login page with centered form: title "SmartWiFi Panel Login", username field, password field (masked), "Enter" button
    - Implement form validation and loading state (disable button, show spinner)
    - Implement JWT token storage and session management in React context
    - Create protected route wrapper redirecting unauthenticated users to login
    - Display session expiration message on token expiry redirect
    - _Requirements: 1.1, 1.4, 1.5, 1.9_

- [ ] 3. Checkpoint - Authentication and isolation verified
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. MikroTik Router Bridge and resilience
  - [ ] 4.1 Implement RouterBridge service with connection pooling
    - Create `services/router_bridge.py` with MikroTik API client (routeros-api library)
    - Implement connection pool per tenant (max 5 concurrent connections)
    - Implement connection timeout (5 seconds) and request timeout (10 seconds)
    - Create queue for requests when all 5 connections are in use (10-second timeout before error)
    - Implement command executor with response translation
    - Implement methods: execute_command, get_devices, add_firewall_rule, remove_firewall_rule, set_queue_rule, delete_queue_rule, test_connection
    - _Requirements: 13.3, 13.4, 13.5_

  - [ ]* 4.2 Write property test for connection pool constraint
    - **Property 33: Connection pool size constraint**
    - **Validates: Requirements 13.3, 13.4**

  - [ ] 4.3 Implement circuit breaker pattern
    - Create `services/circuit_breaker.py` with state machine (Closed, Open, Half-Open)
    - Implement failure counter: 5 consecutive failures in 60s → Open state
    - Implement 30-second pause then probe command for Half-Open transition
    - Implement automatic recovery (probe success → Closed) or re-open (probe fail → Open, schedule next probe in 30s)
    - Emit circuit breaker state change events for WebSocket broadcasting
    - _Requirements: 12.4, 12.5, 12.7, 12.8_

  - [ ]* 4.4 Write property test for circuit breaker state transitions
    - **Property 31: Circuit breaker state transitions**
    - **Validates: Requirements 12.4, 12.7, 12.8**

  - [ ] 4.5 Implement retry with exponential backoff
    - Create retry decorator/utility with backoff pattern: 1s, 2s, 4s (max 3 retries)
    - Integrate with circuit breaker failure counter
    - Log each retry attempt with timestamp and error details
    - _Requirements: 12.2, 12.3_

  - [ ]* 4.6 Write property test for exponential backoff timing
    - **Property 30: Exponential backoff timing**
    - **Validates: Requirements 12.2**

  - [ ] 4.7 Implement router configuration and connection test
    - Create settings endpoints: `GET /api/settings/router`, `PUT /api/settings/router`, `POST /api/settings/router/test`
    - Implement AES-256-GCM encryption for router passwords (key from env, IV stored with ciphertext)
    - Implement connection test with 10-second timeout
    - Validate IP format (IPv4: four octets 0-255) and port range (1-65535)
    - Store connection status and last_connected timestamp
    - Implement auto-reconnection: retry every 30 seconds, max 10 attempts, then stop until manual trigger
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.7, 9.8_

  - [ ]* 4.8 Write property tests for router configuration
    - **Property 25: Router configuration validation**
    - **Property 26: Router credential encryption round-trip**
    - **Validates: Requirements 9.3, 9.4**

  - [ ]* 4.9 Write property test for slow router tenant isolation
    - **Property 34: Slow router tenant isolation**
    - **Validates: Requirements 13.5**

- [ ] 5. Device Management
  - [ ] 5.1 Implement device service and CRUD endpoints
    - Create `services/device_service.py` with device listing, status tracking
    - Implement `GET /api/devices` endpoint returning all tenant devices with status, IP, MAC, hostname, manufacturer, usage
    - Implement device polling from MikroTik router (active connections list)
    - Implement device status tracking (Active/Blocked) with Redis cache (10s TTL)
    - Track per-device session data usage in DeviceSession table
    - _Requirements: 4.1, 4.5, 4.6, 13.6_

  - [ ] 5.2 Implement device actions (kick, block, unblock, limit)
    - Implement `POST /api/devices/{mac}/kick` - disconnect device via MikroTik API within 2 seconds
    - Implement `POST /api/devices/{mac}/block` - add MAC to MikroTik blacklist permanently
    - Implement `POST /api/devices/{mac}/unblock` - remove MAC from blacklist within 2 seconds
    - Implement `POST /api/devices/{mac}/limit` - create queue rule (1-100 Mbps download and upload)
    - Implement `DELETE /api/devices/{mac}/limit` - delete queue rule within 2 seconds
    - Return specific error message on MikroTik failure (kick, block, or limit)
    - _Requirements: 4.2, 4.3, 4.4, 4.8, 4.10, 4.11_

  - [ ]* 5.3 Write property tests for device management
    - **Property 8: Device block/unblock round-trip**
    - **Property 9: Speed limit queue rule round-trip**
    - **Validates: Requirements 4.3, 4.4, 4.10, 4.11**

  - [ ] 5.4 Implement OUI manufacturer lookup
    - Create `services/oui_lookup.py` with MAC address prefix to manufacturer mapping
    - Load OUI database (IEEE MA-L) into memory or Redis cache
    - Return manufacturer name and logo URL for known prefixes
    - Return "Unknown Manufacturer" with placeholder icon for unknown prefixes
    - _Requirements: 4.7, 4.9_

  - [ ]* 5.5 Write property test for OUI resolution
    - **Property 10: OUI manufacturer resolution**
    - **Validates: Requirements 4.7, 4.9**

  - [ ]* 5.6 Write property test for cache staleness
    - **Property 35: Cache staleness enforcement**
    - **Validates: Requirements 13.6**

- [ ] 6. Application Blocking
  - [ ] 6.1 Implement blocking service and scenario management
    - Create `services/blocking_service.py` with scenario CRUD and rule management
    - Implement `GET /api/blocking/scenarios` listing all scenarios with active status
    - Seed database with default blocking scenarios (Instagram, TikTok, Telegram, YouTube, Netflix) including Layer7, TLS, and DNS rule definitions
    - Store versioned rule sets in blocking_scenario.rule_definitions (JSONB)
    - _Requirements: 5.1, 5.7_

  - [ ] 6.2 Implement blocking scenario activation and deactivation
    - Implement `POST /api/blocking/scenarios/{id}/activate` - apply all rules to MikroTik
    - Implement `POST /api/blocking/scenarios/{id}/deactivate` - remove all rules from MikroTik
    - Apply rules in sequence: Layer7, TLS, DNS for each scenario
    - Complete full rule application cycle within 3 seconds
    - Ensure blocking rules do NOT apply to VIP devices (bypass all restrictions)
    - Implement rule verification: confirm rules appear in MikroTik active config within 5 seconds
    - Implement retry on verification failure (1 retry, then rollback partial rules and notify admin)
    - Handle router unreachable: preserve current state, revert toggle, notify admin
    - Implement CPU load check: queue rules if router CPU > 80%, retry at 30s intervals (max 5 attempts before failure)
    - _Requirements: 5.2, 5.3, 5.4, 5.5, 5.6, 5.8, 5.9, 5.10_

  - [ ]* 6.3 Write property tests for application blocking
    - **Property 11: Blocking scenario rule round-trip**
    - **Property 12: VIP device blocking exemption**
    - **Property 13: Router unreachable state preservation**
    - **Validates: Requirements 5.2, 5.3, 5.5, 5.10**

- [ ] 7. Bandwidth Control
  - [ ] 7.1 Implement bandwidth service and global limits
    - Create `services/bandwidth_service.py` with global limit management
    - Implement `GET /api/bandwidth/config` returning current configuration including uplink capacity
    - Implement `PUT /api/bandwidth/global` setting global download/upload limits (1-1000 Mbps, 1 Mbps increments)
    - Apply MikroTik simple queue rules to all non-VIP devices within 3 seconds
    - Handle router unreachable with retry (3 attempts, 5-second intervals)
    - _Requirements: 6.1, 6.2, 6.8_

  - [ ] 7.2 Implement VIP device management and per-device overrides
    - Implement `POST /api/devices/{mac}/vip` - add to VIP list, remove all existing queue rules
    - Implement `DELETE /api/devices/{mac}/vip` - remove from VIP, apply current global limit
    - Implement `GET /api/bandwidth/vip` listing VIP devices (max 50)
    - Implement per-device bandwidth override (1-1000 Mbps) taking precedence over global limit
    - Implement congestion warning when total allocated bandwidth exceeds admin-configured uplink capacity
    - _Requirements: 6.3, 6.4, 6.5, 6.6, 6.7_

  - [ ]* 7.3 Write property tests for bandwidth control
    - **Property 14: Global bandwidth applies only to non-VIP devices**
    - **Property 15: VIP status queue rule round-trip**
    - **Property 16: Per-device bandwidth override precedence**
    - **Property 17: Bandwidth overallocation warning**
    - **Validates: Requirements 6.2, 6.4, 6.5, 6.6, 6.7**

- [ ] 8. Checkpoint - Core backend services verified
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Real-Time Communication
  - [ ] 9.1 Implement WebSocket manager
    - Create `services/websocket_manager.py` with connection registry per tenant
    - Implement WebSocket endpoint `wss://{host}/ws?token={jwt_token}` with JWT authentication
    - Establish WebSocket connection within 3 seconds of successful authentication
    - Support at least 10 concurrent connections per tenant
    - Implement Redis Pub/Sub for cross-instance message broadcasting
    - Implement heartbeat ping/pong for connection health monitoring
    - Implement channel subscription (client → server `subscribe` event)
    - _Requirements: 10.1, 10.2, 10.6_

  - [ ] 9.2 Implement WebSocket event broadcasting
    - Implement server→client events: device.status_update, device.connected, device.disconnected, traffic.stats (every 3s), traffic.graph_point (every 2s), alert.new, blocking.status_change, router.connection_status, circuit_breaker.state_change
    - Push device status changes within 2 seconds of occurrence
    - Push anomaly alerts within 5 seconds of detection
    - Implement full state sync on reconnection (send all current device statuses, traffic stats, active alerts)
    - _Requirements: 3.2, 3.5, 3.6, 4.5, 4.6, 10.2, 10.5_

  - [ ]* 9.3 Write property test for WebSocket state synchronization
    - **Property 27: WebSocket state synchronization completeness**
    - **Validates: Requirements 10.5**

  - [ ] 9.4 Implement frontend WebSocket provider with fallback
    - Create React context `WebSocketProvider` managing WS connection lifecycle
    - Implement automatic reconnection: retry every 5 seconds, max 12 attempts (60 seconds total)
    - Implement HTTP polling fallback at 10-second intervals after max reconnection attempts exceeded
    - Display connection status indicator (connected/disconnected/reconnecting)
    - Retain last received data on screen during disconnection
    - Display indicator that real-time updates are unavailable when using HTTP polling fallback
    - _Requirements: 3.7, 3.8, 10.3, 10.4, 10.7_

- [ ] 10. AI Traffic Analysis
  - [ ] 10.1 Implement NetFlow data collector
    - Create `services/netflow_collector.py` polling MikroTik router every 60 seconds
    - Extract traffic metadata: src/dst IP, port, protocol, bytes, packets
    - Store raw traffic data in traffic_data table (partitioned by month)
    - Implement data retention: raw data 30 days, hourly aggregates 1 year
    - Generate medium-severity connectivity alert if 3+ consecutive collection intervals fail
    - _Requirements: 7.1, 7.10_

  - [ ] 10.2 Implement traffic classifier with K-Means
    - Create `services/traffic_analyzer.py` with K-Means clustering using Scikit-learn
    - Extract features: bytes per flow, packets per flow, flow duration, port distributions, destination diversity
    - Classify traffic into categories: Video, Social Media, Web Browsing, Gaming, File Transfer, Other
    - Store classification results in traffic_data.category field
    - Run as Celery background task
    - _Requirements: 7.2, 7.3_

  - [ ]* 10.3 Write property test for traffic classification
    - **Property 18: Traffic classification correctness**
    - **Validates: Requirements 7.2**

  - [ ] 10.4 Implement anomaly detector with Isolation Forest
    - Create `services/anomaly_detector.py` using Scikit-learn Isolation Forest algorithm
    - Establish baseline from minimum 7 days of historical data per tenant
    - Skip anomaly detection for tenants with < 7 days of data (set learning indicator)
    - Detect deviations > 3 standard deviations from baseline
    - Classify severity: low (3-4 std), medium (4-5 std), high (>5 std)
    - Generate anomaly alerts with severity, anomaly type (volume spike/drop/unusual pattern), observed vs baseline values
    - Push alerts via WebSocket within 5 seconds of detection
    - _Requirements: 7.5, 7.6, 7.7, 7.8_

  - [ ]* 10.5 Write property tests for anomaly detection
    - **Property 19: Anomaly detection baseline requirement**
    - **Property 20: Anomaly severity classification**
    - **Validates: Requirements 7.6, 7.7**

  - [ ] 10.6 Implement malware signature scanner
    - Create `services/malware_scanner.py` with pattern matching
    - Detect C2 patterns: packets < 100 bytes to 10+ distinct destinations within 60 seconds
    - Detect DNS abuse: > 50 queries/second to non-standard resolvers
    - Generate high-severity security alerts on detection
    - _Requirements: 7.9_

  - [ ]* 10.7 Write property test for malware detection
    - **Property 21: Malware signature detection**
    - **Validates: Requirements 7.9**

- [ ] 11. Report Generation
  - [ ] 11.1 Implement report service with Celery async tasks
    - Create `services/report_service.py` with PDF and Excel generation
    - Implement `POST /api/reports/generate` triggering async Celery task
    - Implement `GET /api/reports/{id}/status` for progress tracking
    - Implement `GET /api/reports/{id}/download` for file retrieval
    - Implement `GET /api/reports` listing available reports
    - Validate time period (max 30 days), reject requests exceeding limit
    - Return error notification if selected period contains no data (instead of generating empty report)
    - _Requirements: 8.1, 8.4, 8.5, 8.7, 8.8, 8.9_

  - [ ] 11.2 Implement PDF report generation
    - Generate formatted PDF with: traffic summary, top 10 devices by usage, traffic distribution chart, and anomaly events for selected time period
    - Complete within 30 seconds for 7-day periods, 90 seconds for 30-day periods
    - Store generated file in object storage with 24-hour expiry
    - _Requirements: 8.2, 8.4_

  - [ ] 11.3 Implement Excel report generation
    - Generate spreadsheet with data tables: hourly traffic volumes, per-device usage, blocked application attempts, and anomaly events for selected time period
    - Complete within 30 seconds for 7-day periods, 90 seconds for 30-day periods
    - Store generated file in object storage with 24-hour expiry
    - _Requirements: 8.3, 8.4_

  - [ ] 11.4 Implement report retention and cleanup
    - Retain reports for 24 hours maximum
    - Enforce max 50 reports per admin (purge oldest when exceeded)
    - Create Celery periodic task for expired report cleanup
    - Allow re-download of retained reports without regeneration
    - _Requirements: 8.6_

  - [ ]* 11.5 Write property tests for report service
    - **Property 22: Report content completeness**
    - **Property 23: Report retention policy**
    - **Property 24: Report period validation**
    - **Validates: Requirements 8.2, 8.3, 8.6, 8.9**

- [ ] 12. Checkpoint - Backend services complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 13. Frontend Dashboard Pages
  - [ ] 13.1 Implement main dashboard overview page
    - Create three info cards: total connected devices (0-9999), current download/upload speed (Mbps, 1 decimal place), network quality (ping ms)
    - Implement live real-time traffic graph (last 60 seconds, scrolling right-to-left, updates every 2s via WebSocket)
    - Implement AI Quick Messages panel on right side showing 5 most recent alerts
    - Implement red warning indicator when ping > 100ms or jitter > 50ms
    - Prepend new AI alerts within 5 seconds of detection
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [ ]* 13.2 Write property test for network quality warning
    - **Property 7: Network quality warning threshold**
    - **Validates: Requirements 3.4**

  - [ ] 13.3 Implement devices page
    - Create device table with columns: device name/MAC with manufacturer logo, IP address, MAC address, status (Active green/Blocked red), session data usage (MB, refreshed every 10s)
    - Implement action buttons: Kick, Block, Unblock, Set Limit, Remove Limit
    - Show generic placeholder icon and "Unknown Manufacturer" for unknown OUI prefixes
    - Real-time updates: new devices appear within 5 seconds, disconnections update within 5 seconds (no page refresh required)
    - _Requirements: 4.1, 4.2, 4.3, 4.5, 4.6, 4.9_

  - [ ] 13.4 Implement restrictions page (application blocking)
    - Create application cards with official brand logos for: Instagram, TikTok, Telegram, YouTube, Netflix
    - Implement toggle switches showing blocked/allowed status
    - Show pending indicator while rule application is in progress
    - Revert toggle on failure with error notification
    - _Requirements: 5.1, 5.11_

  - [ ] 13.5 Implement restrictions page (bandwidth control)
    - Create global bandwidth slider (1-1000 Mbps, 1 Mbps increments) for download and upload
    - Create VIP device list management (add/remove, max 50 devices)
    - Create per-device bandwidth override input (1-1000 Mbps)
    - Display congestion warning when total allocation exceeds uplink capacity
    - _Requirements: 6.1, 6.3, 6.6, 6.7_

  - [ ] 13.6 Implement analytics page
    - Create traffic distribution pie chart (Video, Social Media, Web Browsing, Gaming, File Transfer, Other) for selected time period
    - Create time-series chart showing MB per hour for selected period
    - Implement period selector (last 24 hours / last 7 days)
    - Display anomaly timeline with severity indicators (low/medium/high)
    - Show baseline learning indicator for tenants with < 7 days data
    - Add PDF and Excel export buttons
    - Display progress indicator during report generation (allow admin to continue using other features)
    - _Requirements: 7.3, 7.4, 7.6, 8.1, 8.5_

  - [ ] 13.7 Implement settings page
    - Create router configuration form: IP address (valid IPv4), API port (1-65535, default 8728), username (max 128 chars), password (max 128 chars)
    - Implement client-side validation (IP format, port range) with field-specific error messages before connection attempt
    - Implement "Test Connection" button with 10-second timeout feedback
    - Display "Connected" status indicator on successful test
    - Show error reason on failure (connection timeout, authentication failure, unreachable host)
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

  - [ ] 13.8 Implement header and navigation components
    - Create left sidebar with icons and labels: Dashboard, Devices, Restrictions, Analytics, Settings
    - Create top header with: admin profile name, router connection status indicator (connected green/disconnected red/connecting with distinct visuals), notification bell with unread count badge
    - Implement connection status updates within 5 seconds of state change
    - Implement router reconnection indicator (auto-reconnect every 30s, max 10 attempts, then persistent disconnected status)
    - _Requirements: 9.6, 9.7, 9.8, 11.3, 11.4, 11.8_

  - [ ] 13.9 Implement notification center
    - Create notification bell with unread count badge (numeric)
    - Display alert toasts for new anomaly alerts, circuit breaker state changes, and router disconnections
    - Implement notification list with read/unread state
    - _Requirements: 7.8, 11.4, 12.5_

  - [ ]* 13.10 Write property test for WCAG contrast compliance
    - **Property 28: WCAG AA contrast compliance**
    - **Validates: Requirements 11.5**

- [ ] 14. Error Handling and Audit
  - [ ] 14.1 Implement structured error response handler
    - Create global exception handler returning consistent error format: {code, message, resolution}
    - Map all error categories to appropriate HTTP status codes (401, 403, 404, 409, 422, 429, 500, 503)
    - Ensure all error responses complete within 2 seconds of receiving the request
    - _Requirements: 12.1_

  - [ ]* 14.2 Write property test for error response format
    - **Property 29: Structured error response format**
    - **Validates: Requirements 12.1**

  - [ ] 14.3 Implement audit logging service
    - Create `services/audit_service.py` logging all MikroTik commands and responses
    - Store: router identifier, attempted command, timestamp of each attempt, result, request/response data
    - Implement 30-day retention with periodic Celery cleanup task
    - _Requirements: 12.3, 12.6_

  - [ ]* 14.4 Write property test for audit log completeness
    - **Property 32: Audit log completeness**
    - **Validates: Requirements 12.3, 12.6**

  - [ ] 14.5 Implement frontend error handling and circuit breaker UI
    - Display circuit breaker banner when router communication is suspended (show 30s estimated recovery time)
    - Display connection failure notifications with retry status
    - Handle and display all backend error responses with user-friendly messages and suggested resolutions
    - _Requirements: 12.5_

- [ ] 15. Responsive UI and Accessibility
  - [ ] 15.1 Implement responsive layout (1024px - 2560px)
    - Ensure all pages render correctly from 1024px to 2560px width
    - No horizontal scrolling, all navigation accessible at all breakpoints
    - Minimum click target size 24x24px for all interactive elements
    - Ensure charts and graphs use colors optimized for dark backgrounds with sufficient contrast (WCAG AA: 4.5:1 text, 3:1 non-text)
    - Page load within 3 seconds on 10 Mbps connection
    - _Requirements: 11.5, 11.6, 11.7_

- [ ] 16. Checkpoint - Frontend complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 17. Integration and Final Wiring
  - [ ] 17.1 Wire frontend to backend API endpoints
    - Create API service layer in frontend with Axios interceptors for JWT token injection
    - Implement request/response error handling with automatic token refresh on expiry
    - Connect all pages to their respective REST endpoints
    - Implement loading states and error states for all API calls
    - _Requirements: 1.2, 1.4_

  - [ ] 17.2 Wire WebSocket events to frontend components
    - Connect WebSocketProvider to all real-time components (dashboard cards, device table, alerts, blocking status)
    - Implement event handlers for all server→client events
    - Ensure state consistency between REST data and WebSocket updates
    - _Requirements: 3.2, 3.6, 4.5, 4.6, 10.2_

  - [ ] 17.3 Implement stateless deployment configuration
    - Ensure all session state stored in Redis (no in-memory state)
    - Configure WebSocket sticky sessions via load balancer headers
    - Verify correct behavior with 2+ backend instances behind load balancer
    - Configure CORS, SSL termination, and WebSocket upgrade headers
    - _Requirements: 13.8_

  - [ ]* 17.4 Write integration tests for end-to-end flows
    - Test login → dashboard → device management flow
    - Test application blocking toggle → router rule verification
    - Test bandwidth control → queue rule verification
    - Test report generation → download flow
    - Test WebSocket disconnect → reconnect → state sync flow
    - _Requirements: 1.2, 4.3, 5.2, 6.2, 8.2, 10.5_

- [ ] 18. Final Checkpoint - All systems integrated
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at key milestones
- Property tests validate the 35 universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- Backend uses Python FastAPI with Hypothesis for property-based testing
- Frontend uses React.js with TypeScript, Tailwind CSS, and Recharts
- All MikroTik communication goes through the RouterBridge with circuit breaker protection
- Redis is used for caching (10s TTL), sessions, pub/sub (cross-instance WebSocket), and rate limiting
- PostgreSQL RLS provides database-level tenant isolation as a second enforcement layer

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["1.3", "1.5", "1.6"] },
    { "id": 2, "tasks": ["1.4"] },
    { "id": 3, "tasks": ["2.1", "2.5"] },
    { "id": 4, "tasks": ["2.2", "2.3", "2.6", "2.7"] },
    { "id": 5, "tasks": ["2.4"] },
    { "id": 6, "tasks": ["4.1", "4.5"] },
    { "id": 7, "tasks": ["4.2", "4.3", "4.7"] },
    { "id": 8, "tasks": ["4.4", "4.6", "4.8", "4.9"] },
    { "id": 9, "tasks": ["5.1", "5.4", "6.1"] },
    { "id": 10, "tasks": ["5.2", "5.5", "5.6", "6.2", "7.1"] },
    { "id": 11, "tasks": ["5.3", "6.3", "7.2"] },
    { "id": 12, "tasks": ["7.3"] },
    { "id": 13, "tasks": ["9.1", "10.1"] },
    { "id": 14, "tasks": ["9.2", "9.4", "10.2", "10.4", "10.6"] },
    { "id": 15, "tasks": ["9.3", "10.3", "10.5", "10.7"] },
    { "id": 16, "tasks": ["11.1", "11.2", "11.3"] },
    { "id": 17, "tasks": ["11.4", "11.5"] },
    { "id": 18, "tasks": ["13.1", "13.3", "13.4", "13.5", "13.6", "13.7"] },
    { "id": 19, "tasks": ["13.2", "13.8", "13.9"] },
    { "id": 20, "tasks": ["13.10", "14.1", "14.3"] },
    { "id": 21, "tasks": ["14.2", "14.4", "14.5", "15.1"] },
    { "id": 22, "tasks": ["17.1", "17.2", "17.3"] },
    { "id": 23, "tasks": ["17.4"] }
  ]
}
```
