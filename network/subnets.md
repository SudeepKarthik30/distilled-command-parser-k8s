# Network Subnet Design & Stateless NACL Architecture (10.20.0.0/16)

**Author:** Thirumalasetty Karthik (Roll 230101007)

---

## 1. Variable Length Subnet Masking (VLSM) Strategy

To optimize address space utilization across the `10.20.0.0/16` CIDR block, subnets are allocated in descending order of required capacity. 
The number of assignable IP addresses for any subnet with prefix length `p` is:
$$N_{\text{usable}} = 2^{(32 - p)} - 2$$
*(accounting for the reserved network address and broadcast address).*

### Capacity Derivations:
1. **Application Tier (`app`)**:
   - Requirement: 1,000 host addresses.
   - Sizing: A `/23` block provides $2^9 - 2 = 510$ hosts (insufficient). A `/22` block yields $2^{10} - 2 = 1,022$ hosts.
   - Allocation: `10.20.0.0/22` (spanning `10.20.0.0` through `10.20.3.255`).

2. **Public / Ingress Tier (`public`)**:
   - Requirement: 250 host addresses.
   - Sizing: A `/25` block provides 126 hosts (insufficient). A `/24` block yields $2^8 - 2 = 254$ hosts.
   - Allocation: `10.20.4.0/24` (spanning `10.20.4.0` through `10.20.4.255`).

3. **Database / Storage Tier (`data`)**:
   - Requirement: 100 host addresses.
   - Sizing: A `/26` block provides 62 hosts (insufficient). A `/25` block yields $2^7 - 2 = 126$ hosts.
   - Allocation: `10.20.5.0/25` (spanning `10.20.5.0` through `10.20.5.127`).

4. **Management & Bastion Tier (`management`)**:
   - Requirement: 20 host addresses.
   - Sizing: A `/28` block provides 14 hosts (insufficient). A `/27` block yields $2^5 - 2 = 30$ hosts.
   - Allocation: `10.20.5.128/27` (spanning `10.20.5.128` through `10.20.5.159`).

---

## 2. Complete Subnet Allocation Table

| Subnet Name | Host Requirement | Network Address | Subnet Mask | Usable Range | Broadcast | Total Usable |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **app** | 1,000 | `10.20.0.0` | `/22` (255.255.252.0) | `10.20.0.1` – `10.20.3.254` | `10.20.3.255` | 1,022 |
| **public** | 250 | `10.20.4.0` | `/24` (255.255.255.0) | `10.20.4.1` – `10.20.4.254` | `10.20.4.255` | 254 |
| **data** | 100 | `10.20.5.0` | `/25` (255.255.255.128) | `10.20.5.1` – `10.20.5.126` | `10.20.5.127` | 126 |
| **management** | 20 | `10.20.5.128` | `/27` (255.255.255.224) | `10.20.5.129` – `10.20.5.158` | `10.20.5.159` | 30 |

---

## 3. Stateless NACL Principles & Evaluation Order

Unlike stateful security groups which track active TCP sessions and automatically permit corresponding return traffic, a **Network Access Control List (NACL) is completely stateless**.
* Each packet crossing the subnet boundary is evaluated independently.
* Both request ingress and response egress must be explicitly permitted.
  - Return traffic from backend application pods on ephemeral ports (`1024-65535`) requires explicit allow rules.
  - Return outbound traffic to public clients on ephemeral ports (`1024-65535`) must also be explicitly permitted.

### The Role of Sequential Rule Evaluation:
Rules are processed strictly in ascending numerical order, terminating on the first matching rule:
1. **Malicious Blocklist Priority**: Block rule 50 targets known hostile range `198.51.100.0/24`. Because rule 50 precedes the general web access rules (rule 100 for HTTP and rule 150 for HTTPS), traffic originating from `198.51.100.0/24` is dropped immediately before reaching any permissive rule.
2. **Implicit Deny**: Any packet not matching an explicit permit rule falls through and is rejected by the default deny behavior.
