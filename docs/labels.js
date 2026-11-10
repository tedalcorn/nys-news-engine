// The names both pages show, in one place so they can't drift apart.
// Outlet category = who published a story (scripts/categories.py assigns the id). Coverage type = what the story is (scripts/classify.py).
const OUTLET_CATS=[
 {id:"albany",name:"Albany specialists",desc:"Outlets built around state government",color:"#b3411f"},
 {id:"national",name:"National and legacy",desc:"National papers, wires and networks",color:"#1c4587"},
 {id:"nyc",name:"New York City",desc:"Papers, stations and beat outlets written for the city",color:"#7b4ea3"},
 {id:"regional",name:"Regional dailies",desc:"Major papers outside the five boroughs",color:"#2a8f8f"},
 {id:"local",name:"Local outlets",desc:"Hidden from Latest by default",color:"#a07a3c"},
 {id:"other",name:"Other sources",desc:"Whatever else Google search finds",color:"#98a1a9"},
 {id:"advocacy",name:"Advocacy and think tanks",desc:"Budget, policy and interest groups",color:"#5b7f3a"},
 {id:"official",name:"Official offices",desc:"Releases tab only; not scored here",color:"var(--fg)"}];
const CAT=Object.fromEntries(OUTLET_CATS.map(c=>[c.id,c]));
// Coverage types: id (classify.py TYPES), name, meaning, points (score.py TYPE_ADJ, plus the Scoring check's own −10 for city and county government).
const COVERAGE_TYPES=[["policy","Policy","State government action or its effects: legislation, the budget, agencies, courts, programs",4],
["campaign","Election coverage","Races and candidates: polls, endorsements, ads, fundraising, debates, race previews",0],
["announcement","Press releases","A press release, or a story that only restates one: grants, ribbon cuttings, appointments",-6],
["other","Other (mostly non-policy)","Whatever fits no other type: sports, business, culture, human interest. A few state-related stories land here too",-15],
["local","City and county government","New York City, county, town or school-district news with no state role",-10],
["blotter","Crime blotter","A crime, arrest, court case, accident or fire with no state policy dimension",-12],
["national","Federal and out-of-state","Federal, other-state or foreign news where New York State is not a party",-15]];
const COVERAGE_NAME=Object.fromEntries(COVERAGE_TYPES.map(t=>[t[0],t[1]]));
