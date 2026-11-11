# aak-f2

A Python client for the F2 ESDH system.

## Installation

The package is available on [PyPI](https://pypi.org/project/aak-f2/):

```sh
pip install aak-f2
```

## Usage

F2 stores cases ("sager"), which hold matters ("akter"), which hold documents.
`aak_f2.shared.F2Client` reads all three. It logs in with OAuth2 and discovers
every URL from the F2-REST service index, so the service index URL is the only
URL it needs.

```python
from aak_f2.shared import F2Client

client = F2Client.from_env()

case = client.get_case(1046444)  # or get_case_by_number("2022 - 60")
for item in client.list_matters(case):
    matter = client.get_matter(item.id)
    for doc_item in client.list_documents(matter):
        document = client.get_document(doc_item.id)
        client.save_content(document, f"/tmp/{document.id}.{document.file_type}")
        pdf = client.get_pdf(document)  # None if F2 has no PDF version
        client.save_pdf(document, f"/tmp/{document.id}.pdf")  # None if no PDF

structure = client.get_case_structure(case)  # all matters and documents at once
```

### Search and parties

Full text search is the primary way to search:

```python
hits = client.fulltext_search_cases("UV", count=1000)
matters = client.fulltext_search_matters("UV")  # count defaults to 100
case = client.get_case(hits[0].id)
```

`count` is the maximum number of hits F2 returns. The services `case-search`
and `matter-search` point to an OpenSearch description document; the client
reads the URL template of the real search from it (once) and fills in the text
and `count`. The result is an ATOM feed, so a hit only has `id`, `title`,
`created`, `updated` (with UTC offset) and `url`; read the full case or matter
by its `id` for the case number and other properties.

F2's filtered search looks up cases and matters by exact properties:

```python
hits = client.search_cases(cpr_number="311299-1234")  # or case_number, title, ...
case = client.get_case(hits[0].id)
matters = client.search_matters(case_number="2022 - 60")

party = client.get_party_by_cpr("311299-1234")  # citizen or company
user = client.get_party_by_login("AZ12345")  # F2 user
```

`search_cases` takes `case_number`, `case_id`, `title`, `cpr_number` and
`external_id`; `search_matters` takes `matter_number`, `matter_id`, `title`,
`case_number` and `cpr_number`. At least one criterion is required. The hits
carry the columns of F2's search result; read the full case or matter by its
`id`. The filtered search returns at most 100 hits and has no `count`.

Cases and matters the F2 user has no access to are left out of a search
result, so an empty result does not prove that nothing matches.

Methods that take a case, matter or document accept either its ID or an object
already read with the client.

### Service index

F2 publishes its services in the service index. `service_index()` returns them
keyed by short name, and `service_url()` fills a service's URL template:

```python
for name, link in sorted(client.service_index().items()):
    print(name, link.href, link.title)

url = client.service_url("party-by-party-number", partyNo="12345")
```

The index is read with authentication, so it shows the services available to
the F2 user. For OpenSearch services such as `case-search`, the index points to
a description document; `opensearch_template("case-search")` returns the URL
template of the real search from it.

### Calling F2-REST directly

For parts of F2-REST the client has no method for, `request` sends any request
to a link or URL, and `get_xml` reads an XML resource:

```python
case = client.get_case(1046444)
element = client.get_xml(case.link("extension-data"))  # xml.etree Element
client.request(
    "POST",
    case.link("update-case-extension-data"),
    json={"Fields": [{"Name": "FieldName", "Value": "Value"}]},
)
rows = client.request("GET", url, params={"P1": "v"}, accept="text/csv").text
```

The requests are authenticated and retried like the client's own, and errors
raise `F2HTTPError`. A URL template is filled from `template_params` in
`request` and from keyword arguments in `get_xml`. `request` returns the
`requests.Response`; other keyword arguments (`params`, `json`, `data`,
`files`, `stream`) are passed on to `requests`.

### Creating and updating cases, matters and documents

In F2, a case holds matters ("akter"), and documents belong to a matter.

```python
case = client.create_case(
    "Ansøgning om tilskud",
    journal_plan_code="00.07.00",  # KLE number
    process_instruction_code="G01",  # KLE handlingsfacet
    responsible="AZ12345",  # login, e-mail, party number or a party object
    properties={"ExternalAccessCode": "Open"},  # other F2 input parameters
)
matter = client.create_matter(
    case, "Ansøgning", access_level="Involved", involved_parties=["AZ12345"]
)
document = client.create_document(matter, "ansøgning.pdf")  # path or bytes
client.update_matter(matter, title="Ansøgning (modtaget)")
client.update_case(case, journal_plan_code="00.07.01", responsible="AZ67890")
```

The KLE classification of a case is given with two arguments:

| Argument | F2 property | Meaning |
| --- | --- | --- |
| `journal_plan_code` | `JournalPlanCode` (patched as `/JournalPlan`) | The **KLE number** ("journalplan"), e.g. `00.07.00` |
| `process_instruction_code` | `ProcessInstructionCode` (patched as `/ProcessInstruction`) | The **KLE handlingsfacet**, e.g. `G01` |

They are read back as `case.journal_plan.abbreviation` and
`case.process_instruction.abbreviation`.

`update_case` and `update_matter` change only the given properties; a list
(involved parties, security groups) replaces the whole list. Other properties
in `properties` use F2's property names and PATCH encoding, which for cases
differ from the creation parameters (`Keyword` instead of `KeywordCode`).

Parties are given as a login (`"AZ12345"`), an e-mail, a party number (`26`),
a `Party`/`PartyItem`, or an F2 PartyReference such as
`{"PartyNo": 26, "OrganizationNo": 5}`. Security groups are given by name or
as an F2 PartyGroupReference.

Creation uses F2's Post-Once-Exactly pattern, so the request that sends the
data is retried safely after network errors.

A matter with an access level other than `All` and no involved parties is only
visible to involved parties, so caseworkers may not find it in the F2 client.
`create_matter` and `update_matter` then issue an `F2AccessWarning` that shows
how to set involved parties. The matter is created anyway. Turn the warning
into an error with `warnings.simplefilter("error", F2AccessWarning)`.

### Errors

All errors are subclasses of `aak_f2.shared.F2Error`. HTTP errors from F2 are
raised as `F2HTTPError`, which carries the `status_code`, the requested `url`
and F2's `message`, `details` and `reason_code` (the last two only when F2
sends them). Two statuses have their own subclasses:

| Exception | Status | Meaning |
| --- | --- | --- |
| `F2NotFoundError` | 404 | Not found, or no access (cases and matters) |
| `F2AccessDeniedError` | 403 | Exists, but no access (documents) |

F2 hides cases and matters the F2 user has no access to, so for those a 404
does not prove that the resource does not exist:

| Resource | Does not exist | Exists, no access |
| --- | --- | --- |
| Case | `F2NotFoundError` | `F2NotFoundError` |
| Matter | `F2NotFoundError` | `F2NotFoundError` |
| Document | `F2NotFoundError` | `F2AccessDeniedError` |

```python
from aak_f2.shared import F2NotFoundError

try:
    case = client.get_case(case_id)
except F2NotFoundError:
    ...  # the case does not exist, or the F2 user has no access to it
```

### Configuration

`F2Client.from_env()` reads these environment variables. Use
`F2Client(F2Config(...))` to configure the client in code instead.

| Variable | Required | Description |
| --- | --- | --- |
| `F2_SERVICE_INDEX_URL` | Yes | URL of the F2-REST service index. |
| `F2_CLIENT_ID` | Yes | OAuth2 client ID from the F2 service provider. |
| `F2_CLIENT_SECRET` | Yes | OAuth2 client secret from the F2 service provider. |
| `F2_USERNAME` | Yes | F2 user the client works as. |
| `F2_PASSWORD` | No | Password of the F2 user, if the installation requires it. |
| `F2_ORGANIZATION_PARTYNO` | No | Party number of the organization to log in to. |
| `F2_TIMEOUT` | No | Request timeout in seconds (default 60). |

### Department modules

`aak_f2.mbu.F2Client` extends the shared client with the method names of MBU's
GetOrganized client (`get_case_metadata`, `document_metadata`, `download`,
`convert_to_pdf`, `contact_lookup`, `upload_document`), so MBU processes can switch ESDH by changing the import.

`upload_document(case_id=..., filename=..., data=...)` creates a new matter on
the case for each upload, titled after the file; pass `access_level` and
`involved_parties` for that matter, or `matter_id` to use an existing matter.
