# Requirements Document

## Introduction

The Smart WiFi Dashboard is a web-based SaaS platform that integrates with MikroTik routers to provide comprehensive network administration capabilities. The system enables business owners and network administrators to manage connected devices, block applications/sites, control bandwidth, and leverage AI-powered traffic analysis through a professional dark-mode dashboard interface.

The architecture consists of three core components: a MikroTik Router (hardware gateway handling physical blocking and speed enforcement), a Web Dashboard (React/Vue frontend with Tailwind CSS), and a Python Backend with AI (FastAPI bridge that translates dashboard commands into MikroTik API calls and performs traffic analysis).

The platform is designed for multi-tenant SaaS deployment, allowing 100+ businesses to independently manage their MikroTik routers through a centralized subscription-based service.

## Glossary

- **Dashboard**: The web-based frontend administration panel built with React.js or Vue.js and Tailwind CSS
- **Backend**: The Python FastAPI server that acts as a bridge between the Dashboard and MikroTik routers
- **MikroTik_Router**: The physical network gateway hardware through which all WiFi users connect; responsible for enforcing blocking rules and speed limits
- **Admin**: An authorized user (network administrator or business owner) who has credentials to access the Dashboard
- **Device**: A WiFi client (phone, laptop, tablet) connected to the MikroTik_Router
- **Layer7_Rule**: A MikroTik protocol-level firewall rule that inspects packet content to identify and block specific applications
- **TLS_Rule**: A MikroTik rule that inspects TLS SNI (Server Name Indication) headers to identify encrypted traffic destinations
- **DNS_Rule**: A MikroTik rule that blocks DNS resolution for specific domains
- **VIP_Device**: A device designated to bypass bandwidth restrictions and receive unlimited speed
- **Traffic_Analyzer**: The AI module (Scikit-learn with Isolation Forest or K-Means) that processes NetFlow data to detect anomalies and classify traffic
- **WebSocket_Connection**: A persistent bidirectional communication channel between the Dashboard and Backend for real-time data updates
- **Tenant**: A single business/organization using the SaaS platform with its own isolated MikroTik_Router configuration
- **NetFlow_Data**: Network traffic metadata collected from the MikroTik_Router including source, destination, protocol, and byte counts
- **Blocking_Scenario**: A predefined set of Layer7_Rules, TLS_Rules, and DNS_Rules stored in the database for blocking a specific application

## Requirements

### Requirement 1: Admin Authentication

**User Story:** As a network administrator, I want to securely log into the dashboard with credentials, so that only authorized personnel can access network management functions.

#### Acceptance Criteria

1. THE Dashboard SHALL display a centered login form with "SmartWiFi Panel Login" title, username field, password field with masked input, and "Enter" button
2. WHEN an Admin submits valid credentials, THE Backend SHALL authenticate the Admin and return a session token with a 30-minute expiry within 2 seconds
3. WHEN an Admin submits invalid credentials, THE Backend SHALL return an authentication error without revealing whether the username or password was incorrect
4. WHILE no valid session token is present, THE Dashboard SHALL redirect all navigation attempts to the login page
5. WHEN a session token expires after 30 minutes of inactivity, THE Dashboard SHALL redirect the Admin to the login page and display a session expiration message
6. IF an IP address exceeds 5 failed login attempts within a 10-minute window, THEN THE Backend SHALL reject further login attempts from that IP and return an error indicating the account is temporarily locked until the window resets
7. IF a brute-force attack is detected (more than 20 failed attempts in 1 hour from a single IP), THEN THE Backend SHALL temporarily block that IP for 30 minutes
8. WHEN an Admin submits credentials, THE Backend SHALL reject the request if the username exceeds 64 characters or the password exceeds 128 characters
9. THE Dashboard SHALL disable the "Enter" button and display a loading indicator while an authentication request is in progress

### Requirement 2: Multi-Tenant Isolation

**User Story:** As a SaaS platform operator, I want each business to have isolated access to only their own router and data, so that tenant data remains private and secure.

#### Acceptance Criteria

1. THE Backend SHALL associate each Tenant with exactly one MikroTik_Router configuration
2. WHEN an Admin authenticates, THE Backend SHALL scope all subsequent API responses to that Admin's Tenant data only for the duration of the authenticated session
3. IF an API request attempts to access resources belonging to a different Tenant, THEN THE Backend SHALL reject the request with an error response indicating access is denied, without revealing the existence or details of the target Tenant's resources
4. WHILE processing any data query, THE Backend SHALL apply tenant-scoping filters before executing the query
5. IF a cross-tenant access attempt is detected, THEN THE Backend SHALL log the attempt with timestamp, source Tenant, and target Tenant identifiers
6. IF a Tenant's associated MikroTik_Router is unreachable, THEN THE Backend SHALL return an error response indicating the router is unavailable while continuing to enforce tenant isolation on all other operations

### Requirement 3: Main Dashboard Overview

**User Story:** As a network administrator, I want to see a real-time overview of my network status at a glance, so that I can quickly assess network health and respond to issues.

#### Acceptance Criteria

1. THE Dashboard SHALL display three info cards at the top of the main page showing: total connected devices count (range 0 to 9,999), current overall download and upload speed in Mbps with one decimal place, and network quality as ping in milliseconds
2. THE Dashboard SHALL display a live real-time traffic graph showing the most recent 60 seconds of data that scrolls from right to left, updating at minimum every 2 seconds via WebSocket_Connection
3. THE Dashboard SHALL display an AI Quick Messages panel on the right side showing the 5 most recent alerts from the Traffic_Analyzer
4. WHILE network ping exceeds 100ms or jitter exceeds 50ms, THE Dashboard SHALL display a red warning indicator on the network quality card
5. WHEN a new AI alert is generated, THE Dashboard SHALL prepend the alert to the AI Quick Messages panel within 5 seconds of detection
6. THE Backend SHALL push updated network statistics to the Dashboard via WebSocket_Connection at intervals no greater than 3 seconds
7. IF the WebSocket_Connection is lost, THEN THE Dashboard SHALL display a connection status indicator showing the disconnected state and SHALL retain the last received data on screen until the connection is re-established
8. WHEN the WebSocket_Connection is re-established after a disconnection, THE Dashboard SHALL resume displaying live data within 5 seconds of reconnection

### Requirement 4: Device Management

**User Story:** As a network administrator, I want to view and manage all connected WiFi devices, so that I can monitor usage and control access for individual clients.

#### Acceptance Criteria

1. THE Dashboard SHALL display a table of all WiFi-connected devices showing: device name (or MAC address if the device name is unavailable) with manufacturer logo, IP address, MAC address, connection status (Active in green or Blocked in red), and current session data usage in MB refreshed every 10 seconds
2. WHEN an Admin clicks the Kick action on a device, THE Backend SHALL send a disconnect command to the MikroTik_Router for that device within 2 seconds
3. WHEN an Admin clicks the Block action on a device, THE Backend SHALL add the device MAC address to the MikroTik_Router blacklist permanently until manually unblocked
4. WHEN an Admin sets a speed Limit on a device, THE Backend SHALL create a MikroTik queue rule limiting that device to the specified download and upload speed in Mbps, accepting values between 1 Mbps and 100 Mbps
5. WHEN a new device connects to the MikroTik_Router, THE Dashboard SHALL add the device to the table within 5 seconds without requiring a page refresh
6. WHEN a device disconnects from the MikroTik_Router, THE Dashboard SHALL update the device status to inactive within 5 seconds
7. THE Backend SHALL resolve device manufacturer names and logos from MAC address OUI (Organizationally Unique Identifier) prefixes
8. IF the MikroTik_Router fails to execute a device action (kick, block, or limit), THEN THE Backend SHALL return an error message specifying the failure reason to the Dashboard
9. IF the MAC address OUI prefix is not found in the lookup database, THEN THE Dashboard SHALL display a generic placeholder icon and "Unknown Manufacturer" as the manufacturer name
10. WHEN an Admin clicks the Unblock action on a blocked device, THE Backend SHALL remove the device MAC address from the MikroTik_Router blacklist within 2 seconds and THE Dashboard SHALL update the device status to Active
11. WHEN an Admin removes a speed Limit from a device, THE Backend SHALL delete the corresponding MikroTik queue rule for that device within 2 seconds

### Requirement 5: Application Blocking

**User Story:** As a network administrator, I want to block specific applications for all WiFi users with a simple toggle, so that I can enforce network usage policies without technical MikroTik knowledge.

#### Acceptance Criteria

1. THE Dashboard SHALL display application cards with official brand logos for at minimum: Instagram, TikTok, Telegram, YouTube, and Netflix, each with a toggle switch indicating blocked or allowed status
2. WHEN an Admin toggles an application to blocked status, THE Backend SHALL retrieve the corresponding Blocking_Scenario from the database and apply Layer7_Rules, TLS_Rules, and DNS_Rules to the MikroTik_Router
3. WHEN an Admin toggles an application to allowed status, THE Backend SHALL remove all associated blocking rules from the MikroTik_Router
4. THE Backend SHALL complete the full blocking rule application cycle (receive command, apply rules, confirm success) within 3 seconds
5. WHEN a blocking rule is applied, THE MikroTik_Router SHALL block the target application for all connected devices except VIP_Devices by dropping matching packets and preventing new connections to the application's domains and IP ranges
6. IF the MikroTik_Router CPU load exceeds 80% during rule application, THEN THE Backend SHALL queue the rule, notify the Admin that the rule will be applied when resources are available, and automatically retry application at 30-second intervals for a maximum of 5 attempts before reporting a failure to the Admin
7. THE Backend SHALL store each Blocking_Scenario with versioned rule sets to support updates when applications change their domain patterns
8. WHEN a Blocking_Scenario is applied, THE Backend SHALL verify rule activation by confirming the rules appear in the MikroTik_Router active configuration within 5 seconds of application
9. IF rule verification fails after application, THEN THE Backend SHALL retry rule application once, and if verification fails again, roll back any partially applied rules and notify the Admin with an error message indicating which application's blocking rules could not be activated
10. IF the Backend cannot communicate with the MikroTik_Router when processing a toggle action, THEN THE Backend SHALL retain the current blocking state unchanged, display the toggle in its previous position, and notify the Admin with an error message indicating the router is unreachable
11. WHEN an Admin toggles an application's blocking status, THE Dashboard SHALL display a pending indicator on the application card until the Backend confirms successful rule application or reports a failure

### Requirement 6: Bandwidth Control

**User Story:** As a network administrator, I want to set global and per-device bandwidth limits, so that I can ensure fair usage and prevent any single user from consuming all available bandwidth.

#### Acceptance Criteria

1. THE Dashboard SHALL provide a slider control to set the maximum download and upload speed (in Mbps, ranging from 1 Mbps to 1000 Mbps in 1 Mbps increments) applied globally to all non-VIP devices
2. WHEN an Admin adjusts the global bandwidth slider, THE Backend SHALL update the MikroTik_Router simple queue rules for all non-VIP devices within 3 seconds
3. THE Dashboard SHALL provide a VIP device list (supporting up to 50 devices) where the Admin can add devices that bypass all bandwidth restrictions
4. WHEN a device is added to the VIP list, THE Backend SHALL remove any existing queue rules for that device on the MikroTik_Router
5. WHEN a device is removed from the VIP list, THE Backend SHALL apply the current global bandwidth limit to that device
6. THE Dashboard SHALL provide a per-device bandwidth override input (in Mbps, ranging from 1 Mbps to 1000 Mbps) that, when set, THE Backend SHALL apply to the MikroTik_Router as a device-specific queue rule taking precedence over the global limit
7. IF the total allocated bandwidth across all devices exceeds the Admin-configured uplink capacity, THEN THE Backend SHALL display a warning to the Admin indicating potential congestion
8. IF the MikroTik_Router is unreachable when applying bandwidth changes, THEN THE Backend SHALL display an error message to the Admin indicating the connection failure and SHALL retry the operation up to 3 times at 5-second intervals

### Requirement 7: AI Traffic Analysis and Anomaly Detection

**User Story:** As a network administrator, I want AI-powered analysis of network traffic patterns, so that I can identify security threats, understand usage patterns, and receive proactive alerts about abnormal behavior.

#### Acceptance Criteria

1. THE Traffic_Analyzer SHALL collect and process NetFlow_Data from the MikroTik_Router at intervals no greater than 60 seconds
2. THE Traffic_Analyzer SHALL classify traffic into categories: Video, Social Media, Web Browsing, Gaming, File Transfer, and Other
3. THE Dashboard SHALL display a traffic distribution pie chart showing percentage breakdown by category for the selected time period (last 24 hours or last 7 days)
4. THE Dashboard SHALL display a time-series chart showing total data transferred in megabytes per hour for the selected time period
5. THE Traffic_Analyzer SHALL establish a baseline traffic pattern using a minimum of 7 days of historical data per Tenant
6. WHILE the Traffic_Analyzer has fewer than 7 days of historical data for a Tenant, THE Traffic_Analyzer SHALL skip anomaly detection for that Tenant and THE Dashboard SHALL display an indicator that baseline learning is in progress
7. WHEN the Traffic_Analyzer detects traffic volume or pattern deviating more than 3 standard deviations from the established baseline, THE Traffic_Analyzer SHALL generate an anomaly alert with severity determined as: low for deviation between 3 and 4 standard deviations, medium for deviation between 4 and 5 standard deviations, and high for deviation greater than 5 standard deviations
8. WHEN an anomaly alert is generated, THE Backend SHALL push the alert to the Dashboard via WebSocket_Connection within 5 seconds, including the severity level (low, medium, high), the anomaly type (volume spike, volume drop, or unusual pattern), and the observed versus baseline values
9. IF the Traffic_Analyzer detects patterns consistent with known malware communication signatures (packets smaller than 100 bytes sent to 10 or more distinct destinations within 60 seconds, or DNS queries exceeding 50 requests per second to non-standard resolvers), THEN THE Traffic_Analyzer SHALL generate a high-severity security alert
10. IF the Traffic_Analyzer fails to receive NetFlow_Data from the MikroTik_Router for 3 or more consecutive collection intervals, THEN THE Traffic_Analyzer SHALL generate a medium-severity connectivity alert and THE Dashboard SHALL display a data collection interruption warning

### Requirement 8: Report Generation

**User Story:** As a network administrator, I want to export network analytics as PDF or Excel reports, so that I can share findings with management and maintain records for compliance.

#### Acceptance Criteria

1. THE Dashboard SHALL provide export buttons for PDF and Excel formats on the AI Analytics page
2. WHEN an Admin requests a PDF report, THE Backend SHALL generate a formatted document containing: traffic summary, top 10 devices by usage, traffic distribution chart, and anomaly events for the selected time period
3. WHEN an Admin requests an Excel report, THE Backend SHALL generate a spreadsheet with raw data tables for: hourly traffic volumes, per-device usage, blocked application attempts, and anomaly events for the selected time period
4. THE Backend SHALL complete report generation within 30 seconds for time periods up to 7 days, and within 90 seconds for time periods up to 30 days
5. WHILE report generation is in progress, THE Dashboard SHALL display a progress indicator and allow the Admin to continue using other features
6. THE Backend SHALL retain generated reports for 24 hours, up to a maximum of 50 reports per Admin, to allow re-download without regeneration
7. IF report generation fails, THEN THE Backend SHALL notify the Admin with an error message indicating the failure reason and allow the Admin to retry the export
8. IF the selected time period contains no data, THEN THE Backend SHALL notify the Admin that no data is available for the selected period instead of generating an empty report
9. THE Dashboard SHALL restrict the selectable time period for report generation to a maximum of 30 days

### Requirement 9: MikroTik Router Configuration

**User Story:** As a network administrator, I want to configure the connection between the dashboard and my MikroTik router, so that the system can communicate with and control my network hardware.

#### Acceptance Criteria

1. THE Dashboard SHALL provide a settings page with fields for: MikroTik_Router IP address (valid IPv4 format), API port (numeric value between 1 and 65535, defaulting to 8728), API username (maximum 128 characters), and API password (maximum 128 characters)
2. WHEN an Admin submits router configuration, THE Backend SHALL validate the input fields and attempt a test connection to the MikroTik_Router using the provided credentials with a connection timeout of 10 seconds
3. IF the Admin submits router configuration with an invalid IP address format or a port number outside the range 1–65535, THEN THE Dashboard SHALL display a validation error indicating the invalid field before attempting a connection
4. WHEN the test connection succeeds, THE Backend SHALL store the credentials encrypted at rest using AES-256 and THE Dashboard SHALL display a "Connected" status indicator in the header
5. IF the test connection fails, THEN THE Backend SHALL return an error message indicating the failure reason (connection timeout, authentication failure, or unreachable host) to the Dashboard
6. WHILE the MikroTik_Router connection is active, THE Dashboard SHALL display a green connection status indicator in the top header
7. WHEN the connection to the MikroTik_Router is lost, THE Dashboard SHALL display a red disconnected indicator and THE Backend SHALL attempt reconnection every 30 seconds for a maximum of 10 attempts
8. IF the Backend fails to reconnect after 10 attempts, THEN THE Dashboard SHALL display a persistent disconnected status and THE Backend SHALL stop reconnection attempts until the Admin manually triggers a new connection test

### Requirement 10: Real-Time Communication

**User Story:** As a network administrator, I want the dashboard to update in real-time without manual refreshing, so that I always see current network status and can respond immediately to events.

#### Acceptance Criteria

1. WHEN the Dashboard completes successful authentication, THE Backend SHALL establish a WebSocket_Connection with the Dashboard within 3 seconds
2. WHILE the WebSocket_Connection is active, THE Backend SHALL push device status changes, traffic statistics, and alerts to the Dashboard within 2 seconds of the event occurring on the Backend, without requiring Dashboard polling
3. WHEN the WebSocket_Connection is interrupted, THE Dashboard SHALL display a reconnection indicator and attempt to re-establish the connection every 5 seconds for a maximum of 12 attempts (60 seconds total)
4. IF the Dashboard exceeds the maximum reconnection attempts without success, THEN THE Dashboard SHALL display a persistent connection failure notification and fall back to HTTP polling at 10-second intervals
5. WHEN the WebSocket_Connection is re-established, THE Backend SHALL send the current state of all device statuses, traffic statistics, and active alerts to the Dashboard to ensure data consistency
6. THE Backend SHALL support at least 10 concurrent WebSocket_Connections from multiple Admin sessions for the same Tenant
7. IF the WebSocket_Connection cannot be initially established, THEN THE Dashboard SHALL fall back to HTTP polling at 10-second intervals and display an indicator that real-time updates are unavailable

### Requirement 11: Dashboard UI Design

**User Story:** As a network administrator, I want a professional, dark-mode interface with clear visual hierarchy, so that I can efficiently manage the network without eye strain during extended sessions.

#### Acceptance Criteria

1. THE Dashboard SHALL use a dark color scheme with dark blue and gray backgrounds as the primary palette
2. THE Dashboard SHALL use green color (#22C55E or similar shade within the green hue range) for active/allowed states and red color (#EF4444 or similar shade within the red hue range) for blocked/alert states
3. THE Dashboard SHALL use a left sidebar navigation menu with icons and labels for: Dashboard, Devices, Restrictions, Analytics, and Settings pages
4. THE Dashboard SHALL display a top header bar containing: admin profile name, MikroTik_Router connection status indicator showing one of three states (connected, disconnected, or connecting) each with a distinct visual treatment, and notification bell with unread count displayed as a numeric badge
5. THE Dashboard SHALL render all charts and graphs with colors optimized for dark backgrounds with sufficient contrast (minimum WCAG AA contrast ratio of 4.5:1 for text elements and 3:1 for non-text graphical elements)
6. THE Dashboard SHALL be responsive and functional on screen widths from 1024px to 2560px, ensuring all navigation elements remain accessible, all content is visible without horizontal scrolling, and interactive elements maintain a minimum click target size of 24x24px
7. WHEN the Dashboard loads any page, THE Dashboard SHALL render the complete page content within 3 seconds assuming a network connection of at least 10 Mbps download speed
8. IF the MikroTik_Router connection is lost while the Dashboard is in use, THEN THE Dashboard SHALL update the connection status indicator to the disconnected state within 5 seconds and display a notification indicating the connection loss

### Requirement 12: Error Handling and Resilience

**User Story:** As a network administrator, I want the system to handle errors gracefully and inform me of issues clearly, so that I can troubleshoot problems and maintain confidence in the system's reliability.

#### Acceptance Criteria

1. WHEN the Backend receives an invalid API request, THE Backend SHALL return a structured error response containing an error code, a human-readable message describing the failure, and a suggested resolution within 2 seconds of receiving the request
2. IF the MikroTik_Router does not respond to a connection attempt within 5 seconds, THEN THE Backend SHALL classify the router as unreachable and retry the operation up to 3 times with exponential backoff (1s, 2s, 4s) before reporting failure
3. WHEN a MikroTik_Router operation fails after all retry attempts are exhausted, THE Backend SHALL log the failure including the router identifier, the attempted command, the timestamp of each attempt, and the error received, and notify the Admin via the Dashboard
4. IF the Backend detects 5 consecutive MikroTik_Router communication failures within a 60-second window, THEN THE Backend SHALL activate the circuit breaker, reject all new router commands with an error indicating temporary unavailability, and attempt a single probe command after a 30-second pause to determine if the router has recovered
5. WHEN the circuit breaker activates, THE Dashboard SHALL display a banner indicating that router communication is suspended and showing the estimated recovery time as 30 seconds from activation
6. THE Backend SHALL log all MikroTik_Router commands and responses for audit purposes with a retention period of 30 days
7. IF the circuit breaker probe command succeeds after the 30-second pause, THEN THE Backend SHALL deactivate the circuit breaker and resume processing queued router commands
8. IF the circuit breaker probe command fails after the 30-second pause, THEN THE Backend SHALL keep the circuit breaker active, notify the Admin via the Dashboard that manual intervention may be required, and schedule another probe attempt after an additional 30 seconds

### Requirement 13: Performance and Scalability

**User Story:** As a SaaS platform operator, I want the system to handle 100+ concurrent tenants efficiently, so that the platform remains responsive as the customer base grows.

#### Acceptance Criteria

1. THE Backend SHALL handle a minimum of 100 concurrent Tenant connections with 95th-percentile response times under 500ms for API requests (excluding report generation)
2. THE Backend SHALL process MikroTik_Router polling for all connected Tenants without exceeding 70% CPU utilization on the server under a sustained load of 100 concurrent Tenants
3. THE Backend SHALL use connection pooling for MikroTik_Router API connections with a maximum of 5 concurrent connections per Tenant
4. IF all 5 pooled connections for a Tenant are in use, THEN THE Backend SHALL queue subsequent requests and return an error indicating connection unavailability if the request is not served within 10 seconds
5. WHEN a Tenant's MikroTik_Router is slow to respond (over 5 seconds), THE Backend SHALL timeout the request, notify the Tenant that the router is unreachable, and continue serving other Tenants with response times remaining under 500ms at the 95th percentile
6. THE Backend SHALL cache device lists and active rules per Tenant with a maximum staleness of 10 seconds to reduce MikroTik_Router API load
7. IF the cache is unavailable, THEN THE Backend SHALL fall back to direct MikroTik_Router API queries without returning an error to the Tenant
8. THE Backend SHALL support horizontal scaling by maintaining stateless request handling with shared session storage, verified by serving requests correctly when at least 2 Backend instances run simultaneously behind a load balancer
