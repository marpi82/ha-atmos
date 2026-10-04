/* Minimal Pages.js excerpt for poll-schedule parsing tests. */
const circID = HOD16[`${circName}_TEPLOTY`];
itemHTML += `
  <input id="ID_HOD16_TEPLOTY" type="hidden" ${Atribut.PrmID5s}="[${circID}]" oninput="WS.PageEngine.Hod16setTempRead()">
`;
HTML += `
  <input ${Atribut.PrmID5s}="[${HOD16.O1_OBECNE}]" oninput="WS.PageEngine.Hod16General(this)">
  <input ${Atribut.PrmID5s}="[${HOD16.O2_OBECNE}]" oninput="WS.PageEngine.Hod16General(this)">
  <input ${Atribut.PrmID5s}="[${HOD16.O3_OBECNE}]" oninput="WS.PageEngine.Hod16General(this)">
  <input ${Atribut.PrmID5s}="[${HOD16.O4_OBECNE}]" oninput="WS.PageEngine.Hod16General(this)">
  <input ${Atribut.PrmID5s}="[${HOD16.TUV_OBECNE}]" oninput="WS.PageEngine.Hod16General(this)">
  <input ${Atribut.PrmID5s}="[${HOD16.O1_REZIM}]" oninput="WS.PageEngine.Hod16Regime(this)">
  <input ${Atribut.PrmID5s}="[${HOD16.O2_REZIM}]" oninput="WS.PageEngine.Hod16Regime(this)">
  <input ${Atribut.PrmID5s}="[${HOD16.O3_REZIM}]" oninput="WS.PageEngine.Hod16Regime(this)">
  <input ${Atribut.PrmID5s}="[${HOD16.O4_REZIM}]" oninput="WS.PageEngine.Hod16Regime(this)">
  <input ${Atribut.PrmID5s}="[${HOD16.TUV_REZIM}]" oninput="WS.PageEngine.Hod16Regime(this)">
  <span ${Atribut.PrmID30s}="[${HOD16.O1_TEPLOTA}]">--,-</span>
  <span ${Atribut.PrmID30s}="[${HOD16.O2_TEPLOTA}]">--,-</span>
  <span ${Atribut.PrmID30s}="[${HOD16.O3_TEPLOTA}]">--,-</span>
  <span ${Atribut.PrmID30s}="[${HOD16.O4_TEPLOTA}]">--,-</span>
  <span ${Atribut.PrmID30s}="[${HOD16.TUV_TEPLOTA}]">--,-</span>
  <span ${Atribut.PrmID30s}="[${HOD16.O1_VLHKOST}]">--,-</span>
  <span ${Atribut.PrmID30s}="[${HOD16.O2_VLHKOST}]">--,-</span>
  <span ${Atribut.PrmID30s}="[${HOD16.O3_VLHKOST}]">--,-</span>
  <span ${Atribut.PrmID30s}="[${HOD16.O4_VLHKOST}]">--,-</span>
  <span ${Atribut.PrmID30s}="[${HOD16.TUV_VLHKOST}]">--,-</span>
  <input ${Atribut.PrmID30s}="[${HOD16.O1_TRVALY_REZIM}]">
`;
