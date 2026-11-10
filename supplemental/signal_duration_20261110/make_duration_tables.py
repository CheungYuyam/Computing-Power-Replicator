"""Render verified complete results; never selects dates or controller seeds."""
import csv,json
from pathlib import Path
ROOT=Path(__file__).parent
BASE=ROOT/'table_exports'
assert json.loads((ROOT/'results/verification.json').read_text())['complete']
data=list(csv.DictReader((ROOT/'results/date_summary.csv').open()))
rows={(r['date'],int(r['duration_h']),r['representation']):r for r in data}
dates=sorted({r['date'] for r in data})
assert len(rows)==27 and len(dates)==3 and all(int(r['seeds'])==3 for r in data)

def val(r,k,stat='mean',digits=2,scale=1):
    v=float(r[k+'_'+stat])*scale
    if abs(v)<.5*10**(-digits):v=0.
    return f'{v:.{digits}f}'

def spread(r,k,digits=2):
    a,b,c=[val(r,k,s,digits) for s in ['mean','min','max']]
    if a==b==c=='0.'+'0'*digits:return '0'
    return r'\shortstack{'+a+r'\\{}['+b+', '+c+']}'

def table(caption,label,columns,head,body,note,appendix=False):
    return ('\\begin{table}['+('H' if appendix else '!htb')+']\n\\color{black}\n'+
        ('\\captionsetup{labelfont={color=black},textfont={color=black}}\n' if appendix else '')+
        '\\caption{'+caption+'}\n\\label{'+label+'}\n\\centering\\footnotesize\n'+
        '\\setlength{\\tabcolsep}{2pt}\n\\renewcommand{\\arraystretch}{1.12}\n'+
        '\\begin{tabular*}{\\columnwidth}{@{\\extracolsep{\\fill}}'+columns+'@{}}\n\\toprule\n'+
        head+'\\\\\n\\midrule\n'+body+'\\bottomrule\n\\end{tabular*}\n\\vspace{3pt}\n'+
        '\\parbox{\\columnwidth}{'+note+'}\n\\end{table}\n')

main=[];scale=[];energy=[];service=[]
for di,date in enumerate(dates):
    if di:
        for a in [main,scale,energy,service]:a.append('\\midrule\n')
    for h in [1,2,4]:
        r,c,a=[rows[date,h,m] for m in ['R','C','A']]
        lead=f'{date[5:] if h==1 else ""} & {h}'
        main.append(lead+' & '+spread(r,'window_target_mean_kw')+' & '+spread(c,'window_target_mean_kw')+'\\\\\n')
        scale.append(lead+' & '+val(r,'recorded_baseline_kwh',digits=3,scale=.001)+' & '+val(c,'discrepancy_mean_kw',digits=3)+' & '+val(c,'discrepancy_percent_recorded',digits=3)+' & '+val(a,'discrepancy_percent_recorded',digits=3)+'\\\\\n')
        energy.append(lead+' & '+' & '.join(spread(r,k) for k in ['window_target_kwh','window_other_kwh','post4_target_kwh','post4_other_kwh'])+'\\\\\n')
        service.append(lead+' & '+spread(r,'actual_completion_delta_pp',3)+' & '+spread(r,'actual_wait_delta_min',3)+'\\\\\n')

files={
 BASE/'Main_Manuscript_LaTeX/tables/response_replay.tex':table(
    'Target-Site Power Response Across Signal Durations','tab:response-replay','lccc',
    r'Date & \shortstack{Duration\\(h)} & \shortstack{Recorded\\starts} & \shortstack{No resource\\waiting}',
    ''.join(main),
    'Signal on minus off, averaged over the active signal window, in kW. Entries give the mean and [minimum, maximum] over three paired seeds. Negative values denote target-site load relief.'),
 BASE/'Appendix_LaTeX/tables/response_scale.tex':table(
    'Scale of the Response Discrepancy Across Signal Durations','tab:app-response-scale','lrrrrr',
    r'Date & \shortstack{Duration\\(h)} & \shortstack{$E_0$\\(MWh)} & \shortstack{$\delta P_C$\\(kW)} & \shortstack{$\epsilon_C$\\(\%)} & \shortstack{$\epsilon_A$\\(\%)}',
    ''.join(scale),
    r'Three-seed means. $E_0$ is recorded target-site energy without the signal over the corresponding window. $\delta P_C$ is the C-minus-R discrepancy in window-average power response. $\epsilon_m=100(\Delta E_m-\Delta E_R)/E_0$; ratios are computed within each pair before averaging. R, C, and A are defined in Section III.6.',True),
 BASE/'Appendix_LaTeX/tables/duration_energy.tex':table(
    'Recorded Demand During and After Signals of Different Durations','tab:app-duration-energy','lccccc',
    r'Date & \shortstack{Duration\\(h)} & \shortstack{Window\\target} & \shortstack{Window\\other sites} & \shortstack{Next 4 h\\target} & \shortstack{Next 4 h\\other sites}',
    ''.join(energy),
    'Signal on minus off in kWh under recorded execution. Each cell gives the mean and [minimum, maximum] across three paired seeds. The four-hour follow-up starts at the end of each signal. Target and other-site changes sum to the system-wide change.',True),
 BASE/'Appendix_LaTeX/tables/duration_service.tex':table(
    'Task-Service Changes Across Signal Durations','tab:app-duration-service','lccc',
    r'Date & \shortstack{Duration\\(h)} & \shortstack{Completion at 48 h\\(percentage points)} & \shortstack{Mean waiting through 72 h\\(min)}',
    ''.join(service),
    'Signal on minus off for the same cohort released during hours 24--48. Each cell gives the mean and [minimum, maximum] across three paired seeds under recorded execution.',True)
}
for p,text in files.items():
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(text,encoding='utf-8')
print('Wrote',len(files),'tables from all 81 validated result rows.')
