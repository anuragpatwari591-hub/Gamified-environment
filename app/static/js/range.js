document.querySelectorAll('input[type=range][id^="s"]').forEach(function (r) {
  var o = document.getElementById("o" + r.id.slice(1));
  if (o) r.addEventListener("input", function () { o.textContent = r.value; });
});
