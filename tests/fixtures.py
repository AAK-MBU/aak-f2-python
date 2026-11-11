"""XML samples based on the examples in the F2-REST documentation."""

CASE_XML = """\
<Case xmlns="http://cbrain.com/casefile/schema/">
  <Id>1046444</Id>
  <CaseNumber>2022 - 60</CaseNumber>
  <Title>Case 1</Title>
  <CreatedDate>2022-02-03T15:31:26.293</CreatedDate>
  <ModifiedDate>2022-02-03T15:34:40</ModifiedDate>
  <Deadline>2022-02-10T15:34:40</Deadline>
  <CprNumber>62419361</CprNumber>
  <ExternalId>AX-2468</ExternalId>
  <F2Guid>672e2cda-e858-f111-a7b3-f40270e03022</F2Guid>
  <Keyword>
    <Title>Change request</Title>
    <Path>Issuetyper/Change request</Path>
    <Code>Emneord_Issuetyper_Change request</Code>
  </Keyword>
  <Keywords>
    <Keyword>
      <Title>Change request</Title>
      <Code>Emneord_Issuetyper_Change request</Code>
    </Keyword>
  </Keywords>
  <JournalPlan>
    <Title>Kommunens styrelse</Title>
    <Abbreviation>00.07.00</Abbreviation>
  </JournalPlan>
  <ProcessInstruction>
    <Title>Sager vedr. generelle forhold</Title>
    <Abbreviation>G01</Abbreviation>
  </ProcessInstruction>
  <Responsible>
    <Name>James Wolt</Name>
    <EMail>jw@cbrain.dk</EMail>
    <Link href="https://f2.example/rest/parties/1006118" rel="self" />
    <Type>User</Type>
    <Id>1006118</Id>
    <PartyNumber>37301</PartyNumber>
    <CPRCVR>120390-2222</CPRCVR>
    <CVR_P />
  </Responsible>
  <Closed>false</Closed>
  <Link href="https://f2.example/rest/cases/1046444" rel="self" title="Case 1" />
  <Link href="https://f2.example/rest/cases/1046444/matters" rel="down" />
  <Link href="https://f2.example/rest/cases/1046444/create-matter"
        rel="http://cbrain.com/casefile/rel/create-matter" />
  <Link href="https://f2.example/rest/cases/1046444/structure"
        rel="http://cbrain.com/casefile/rel/structure" />
  <Link href="https://f2.example/rest/cases/1046444/extension-data"
        rel="http://cbrain.com/casefile/rel/extension-data" />
  <Link href="https://f2.example/rest/cases/1046444/update-extension-data"
        rel="http://cbrain.com/casefile/rel/update-case-extension-data" />
  <InvolvedParties>
    <InvolvedParty>
      <Name>Kirsten Svanholm-Nielsen</Name>
      <Type>External</Type>
      <PartyNumber>39938</PartyNumber>
      <CPRCVR>070761-4218</CPRCVR>
    </InvolvedParty>
  </InvolvedParties>
</Case>
"""

CASE_STRUCTURE_XML = """\
<Case xmlns="http://cbrain.com/casefile/schema/"
      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <Id>1046444</Id>
  <CaseNumber>2022 - 60</CaseNumber>
  <Title>Case 1</Title>
  <Matters>
    <Matter>
      <Id>517886</Id>
      <MatterNumber>13249</MatterNumber>
      <Title>Example matter</Title>
      <CaseNumber>2022 - 60</CaseNumber>
      <Archived>false</Archived>
      <Deadline xsi:nil="true" />
      <Status>InProgress</Status>
      <Documents>
        <Document>
          <Id>378054</Id>
          <Title>Photo2</Title>
          <FileType>gif</FileType>
        </Document>
      </Documents>
      <Link href="https://f2.example/rest/matters/517886" rel="self" />
    </Matter>
  </Matters>
</Case>
"""

MATTER_XML = """\
<Matter xmlns="http://cbrain.com/casefile/schema/">
  <Id>517886</Id>
  <MatterNumber>13249</MatterNumber>
  <CaseMatterNumber>1</CaseMatterNumber>
  <Title>Borgerhenvendelse</Title>
  <Type>Inbound</Type>
  <CaseNumber>2022 - 60</CaseNumber>
  <Text>Tekst</Text>
  <AccessLevel>All</AccessLevel>
  <Status>InProgress</Status>
  <Archived>true</Archived>
  <DocumentsLocked>false</DocumentsLocked>
  <Receivers>
    <Receiver><Name>cBrain DK</Name><EMail>dk@cbrain.dk</EMail></Receiver>
    <Receiver><Name>cBrain US</Name><EMail>info@cbrain.com</EMail></Receiver>
  </Receivers>
  <Link href="https://f2.example/rest/matters/517886" rel="self" />
  <Link href="https://f2.example/rest/matters/517886/documents" rel="down" />
  <Link href="https://f2.example/rest/cases/1046444" rel="up" />
  <Link href="https://f2.example/rest/matters/517886/create-document"
        rel="http://cbrain.com/casefile/rel/create-document" />
  <Link href="https://f2.example/rest/matters/517886/extension-data"
        rel="http://cbrain.com/casefile/rel/extension-data" />
  <Link href="https://f2.example/rest/matters/517886/update-extension-data"
        rel="http://cbrain.com/casefile/rel/update-matter-extension-data" />
</Matter>
"""

COLLECTION_XML = """\
<Collection xmlns="http://cbrain.com/casefile/schema/">
  <Title>Documents for matter 'Borgerhenvendelse'</Title>
  <Link href="https://f2.example/rest/matters/517886/documents" rel="self" />
  <Items>
    <Item>
      <Id>378053</Id>
      <Title>DossierDocument</Title>
      <Link href="https://f2.example/rest/documents/378053" rel="self" />
    </Item>
    <Item>
      <Id>378054</Id>
      <Title>Photo2.gif</Title>
      <Link href="https://f2.example/rest/documents/378054" rel="self" />
    </Item>
  </Items>
</Collection>
"""

DOCUMENT_XML = """\
<Document xmlns="http://cbrain.com/casefile/schema/">
  <Id>378054</Id>
  <Title>Test document</Title>
  <ModifiedDate>2022-03-30T08:49:16.27</ModifiedDate>
  <Description>Blah blah ...</Description>
  <FileType>html</FileType>
  <ContentType>text/html</ContentType>
  <Size>31</Size>
  <F2Guid>672e2cda-e858-f111-a7b3-f40270e03087</F2Guid>
  <PreferredAttachmentFormat />
  <Link href="https://f2.example/rest/documents/378054" rel="self" />
  <Link href="https://f2.example/rest/matters/517886" rel="up" />
  <Link href="https://f2.example/rest/documents/378054/content"
        rel="http://cbrain.com/casefile/rel/content" />
  <Link href="https://f2.example/rest/documents/378054/pdf"
        rel="http://cbrain.com/casefile/rel/pdf-content" />
</Document>
"""

DOCUMENT_WITHOUT_PDF_XML = DOCUMENT_XML.replace(
    """  <Link href="https://f2.example/rest/documents/378054/pdf"
        rel="http://cbrain.com/casefile/rel/pdf-content" />
""",
    "",
)

ERROR_XML = """\
<Error xmlns="http://cbrain.com/casefile/schema/">
  <Message>The case is closed.</Message>
  <Details>Case 1046444 is closed.</Details>
  <ReasonCode>DossierCaseClosed</ReasonCode>
</Error>
"""

CASE_SEARCH_CSV = (
    "Id,CaseNumber,Title,CprNumber,ExternalId,Created,Updated,alternate\r\n"
    '"279666","2022 - 1172","Sag om Søren Ærø","311299-1234","P2103568",'
    '"2022-03-29T11:00:58","2022-03-29T11:00:58","https://f2.example/rest/cases/279666"'
    "\r\n"
)

MATTER_SEARCH_CSV = (
    "Id,MatterNumber,Title,CaseNumber,CprNumber,Type,AccessLevel,Deadline,"
    "Archived,Status,Created,Updated,alternate\r\n"
    '"279655","13249","Test dossier","2022 - 1170","","Inbound","All","",'
    '"True","InProgress","2022-03-29T10:44:18","2022-03-29T10:44:19",'
    '"https://f2.example/rest/matters/279655"\r\n'
)

EXTERNAL_PARTY_XML = """\
<External xmlns="http://cbrain.com/casefile/schema/">
  <Id>400775</Id>
  <Name>Søren Ærø</Name>
  <PartyNumber>39938</PartyNumber>
  <PartyType>Borger</PartyType>
  <Address1>Helevejen 1</Address1>
  <Address2 />
  <City>Egebjerg</City>
  <CountryCode>DK</CountryCode>
  <CVRCPR>311299-1234</CVRCPR>
  <EMail>soren@example.dk</EMail>
  <PostalCode>2751</PostalCode>
  <ProtectedAddress>false</ProtectedAddress>
  <SynchronizationKey>xpq123</SynchronizationKey>
  <Organization>
    <Name>Aarhus Kommune</Name>
    <Type>Unit</Type>
    <Id>2156</Id>
    <PartyNumber>20</PartyNumber>
  </Organization>
  <Link href="https://f2.example/rest/parties/400775" rel="self" />
</External>
"""

USER_XML = """\
<User xmlns="http://cbrain.com/casefile/schema/">
  <Id>400776</Id>
  <Name>The Boss</Name>
  <Initials>AZ12345</Initials>
  <Link href="https://f2.example/rest/parties/400776" rel="self" />
</User>
"""

EXTENSIONS_XML = """\
<Extensions xmlns="http://cbrain.com/casefile/schema/">
  <Extension>
    <ProcessName>Abc</ProcessName>
    <Data><Size xmlns="http://123">10</Size></Data>
  </Extension>
  <Extension>
    <ProcessName>Xyz</ProcessName>
    <Data><Position xmlns="http://123">20,10</Position></Data>
  </Extension>
  <Link href="https://f2.example/rest/cases/1046444/extension-data" rel="self"
        type="application/vnd.cbrain.casefile+xml" title="Extensions" />
</Extensions>
"""
