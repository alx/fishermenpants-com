/* Fishermen Pants — shipping country selector (persisted, no backend). */
(function () {
  const KEY = "fp_country";
  const COUNTRIES = [
    "Afghanistan","Albania","Algeria","Andorra","Angola","Argentina","Armenia","Australia","Austria","Azerbaijan",
    "Bangladesh","Belgium","Belize","Benin","Bosnia and Herzegovina","Botswana","Brazil","Brunei","Bulgaria","Burkina Faso","Burundi","Cambodia","Cameroon","Canada","Chad","Chile","China","Colombia","Congo (Dem. Rep.)","Costa Rica","Croatia","Cuba","Cyprus","Czechia","Denmark","Djibouti","Dominican Republic","Ecuador","Egypt","El Salvador","Estonia","Ethiopia","Fiji","Finland","France","Gabon","Gambia","Georgia","Germany","Ghana","Greece","Grenada","Guatemala","Guinea","Guyana","Haiti","Honduras","Hungary","Iceland","India","Indonesia","Ireland","Israel","Italy","Ivory Coast","Jamaica","Japan","Jordan","Kazakhstan","Kenya","Kiribati","Kosovo","Kosovo","Kuwait","Kyrgyzstan","Laos","Latvia","Lebanon","Lesotho","Liberia","Libya","Liechtenstein","Lithuania","Luxembourg","Madagascar","Malaysia","Maldives","Mali","Malta","Mauritania","Mauritius","Mexico","Moldova","Monaco","Mongolia","Montenegro","Morocco","Mozambique","Myanmar","Namibia","Nepal","Netherlands","New Zealand","Nicaragua","Niger","Nigeria","North Macedonia","Norway","Oman","Pakistan","Panama","Paraguay","Peru","Philippines","Poland","Portugal","Qatar","Romania","Russia","Rwanda","Saudi Arabia","Senegal","Serbia","Singapore","Slovakia","Slovenia","Somalia","South Africa","South Korea","Spain","Sri Lanka","Sudan","Suriname","Sweden","Switzerland","Syria","Tajikistan","Tanzania","Thailand","Timor-Leste","Togo","Tonga","Trinidad and Tobago","Tunisia","Turkey","Turkmenistan","Tuvalu","Uganda","Ukraine","United Arab Emirates","United Kingdom","United States","Uruguay","Uzbekistan","Vatican City","Venezuela","Vietnam","Yemen","Zambia","Zimbabwe"
  ];
  const saved = localStorage.getItem(KEY);

  function populate(sel) {
    if (!sel) return;
    sel.innerHTML = '<option value="">Select country</option>' +
      COUNTRIES.map(c => `<option value="${c}">${c}</option>`).join("");
    if (saved) sel.value = saved;
    sel.onchange = () => {
      localStorage.setItem(KEY, sel.value);
      document.querySelectorAll(".country-select").forEach(x => { if (x !== sel) x.value = sel.value; });
      document.dispatchEvent(new CustomEvent("fp:country", { detail: sel.value }));
    };
  }
  populate(document.getElementById("country-select-footer"));
  populate(document.getElementById("country-select-cart"));
})();
