**1\. Legal Disclaimer**

**DISCLAIMER OF LIABILITY AND WARRANTIES**

THE PLATFORM (INCLUDING ANY FEATURES, TOOLS, SCRIPTS, OR INTEGRATIONS RELATED TO SIGNAL MESSENGER OR ANY THIRD-PARTY SERVICES) IS PROVIDED "AS IS" AND "AS AVAILABLE" WITHOUT ANY WARRANTIES OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, ACCURACY, RELIABILITY, COMPLETENESS, TIMELINESS, OR NON-INFRINGEMENT.

WE (THE PLATFORM OPERATORS, DEVELOPERS, AND AFFILIATES) DO NOT OWN, OPERATE, CONTROL, OR ENDORSE SIGNAL MESSENGER OR ANY DATA DERIVED FROM IT. ALL INFORMATION, GROUP LINKS, USER IDENTIFIERS, PHONE NUMBERS, SERVICE IDs, MEDIA, MESSAGES, OR OTHER DATA OBTAINED FROM OR RELATED TO SIGNAL IS SOURCED FROM PUBLICLY ACCESSIBLE OR USER-PROVIDED SOURCES AND MAY BE INCOMPLETE, OUTDATED, INACCURATE, MISLEADING, OR SUBJECT TO CHANGE WITHOUT NOTICE.

BY ACCESSING, USING, OR RELYING ON THE PLATFORM, YOU ACKNOWLEDGE AND AGREE THAT:

* WE ARE NOT RESPONSIBLE FOR THE ACCURACY, VALIDITY, AVAILABILITY, OR INTEGRITY OF ANY DATA, INCLUDING BUT NOT LIMITED TO SIGNAL GROUP LINKS, USER PROFILES, PHONE NUMBERS, SERVICE IDs, OR ASSOCIATED METADATA.  
* USE OF THE PLATFORM IS AT YOUR SOLE RISK. WE SHALL NOT BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, PUNITIVE, OR EXEMPLARY DAMAGES ARISING FROM OR RELATED TO YOUR USE OF THE PLATFORM, INCLUDING BUT NOT LIMITED TO LOSS OF DATA, PROFITS, GOODWILL, BUSINESS OPPORTUNITIES, OR ANY OTHER INTANGIBLE LOSSES, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.  
* YOU HEREBY RELEASE, WAIVE, DISCHARGE, AND COVENANT NOT TO SUE US, OUR OFFICERS, DIRECTORS, EMPLOYEES, AGENTS, OR AFFILIATES FROM ANY AND ALL LIABILITY, CLAIMS, DEMANDS, ACTIONS, OR CAUSES OF ACTION WHATSOEVER ARISING OUT OF OR RELATED TO YOUR USE OF THE PLATFORM OR ANY INFORMATION PROVIDED THEREIN.

THIS DISCLAIMER SHALL SURVIVE TERMINATION OF YOUR ACCESS TO THE PLATFORM.

**2\. Technical Documentation: Signal Integration Notes**

**Signal Group Links and Ephemeral Nature**  
Signal group invite links (also known as group links or QR codes for joining groups) are inherently ephemeral and dynamic. They encode group parameters that can change at any time due to administrative actions, such as:

* Regeneration of the invite link by a group admin.  
* Changes to group membership, permissions, or approval settings (e.g., enabling/disabling admin approval for link joins).  
* Group upgrades (e.g., from legacy to new group formats).  
* Profile refreshes or version mismatches among members/devices.

As a result, a previously valid group link may become invalid or redirect incorrectly without warning. To maintain reliable access or membership resolution, group links require constant refreshing—ideally via periodic re-fetching from known group members, admins, or alternative discovery mechanisms. Scripts or background workers attempting to derive or validate the most recent link from group parameters must account for this volatility and implement retry/fallback logic.

**Signal User Identifiers: Usernames, Phone Numbers, and Service IDs**

* **Usernames** in Signal are ephemeral by design. They serve solely as a discoverable, shareable token to initiate contact without revealing a phone number. Usernames can be created, changed, or deleted at any time by the user (with a required numeric discriminator, e.g., example.123). Once changed or deleted, a username can no longer be reliably associated with the account in the short term, and Signal provides no public directory or search for them.  
* **Phone numbers** remain the underlying registration identifier for all Signal accounts (required at signup). However, privacy settings allow users to hide visibility and discoverability ("Who can see my number" / "Who can find me by number" set to "Nobody"). Approximately half of active Signal users (rough estimate based on privacy trends and optional exposure) intentionally expose or make their phone numbers discoverable/findable via contacts or settings, while the other half prioritize hiding them.  
* **Service IDs** (also referred to as ACI – Anonymous Credential Identifier – or the internal UUID/Service UUID in Signal's protocol) are the permanent, stable identifier for a Signal account. Unlike usernames or phone numbers, Service IDs do not change and persist across username/profile modifications. For reliable long-term tracking or deduplication in tools/scripts that interact with Signal data, mapping via phone number to Service ID (where possible) or direct Service ID usage is the most robust approach, as it avoids reliance on ephemeral surface-level identifiers.

**Recommendations for Tools/Scripts Interacting with Signal Data**

* Prefer Service ID as the canonical identifier for persistence.  
* Implement aggressive refreshing and validation for group links/parameters.  
* Handle cases where phone numbers are hidden (no discovery) or usernames are rotated.  
* Always cross-reference with Signal's official support/docs for protocol changes, as identifiers and behaviors evolve.

