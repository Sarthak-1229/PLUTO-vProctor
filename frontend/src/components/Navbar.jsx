import React from 'react'
import {
  ShieldCheck,
  Sliders,
  History,
  CheckCircle2,
  ChevronRight,
  Flame,
} from 'lucide-react'
import plutoLogo from '../assets/logo.png'

export function Navbar({
  steps,
  currentStep,
  onStepClick,
  activePreset,
  onOpenSettings,
  onOpenDashboard,
}) {
  const currentIdx = steps.findIndex((s) => s.id === currentStep)

  return (
    <header className="border-b-[3px] border-black bg-white sticky top-0 z-40 shadow-[0_4px_0_0_#000]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
        {/* Brand */}
        <div className="flex items-center space-x-3 cursor-pointer" onClick={() => onStepClick && onStepClick('select')}>
          <div className="w-10 h-10 border-2 border-black rounded-xl overflow-hidden bg-[#FFE600] flex items-center justify-center shadow-[2px_2px_0px_0px_#000] rotate-[-2deg]">
            <img src={plutoLogo} alt="PLUTO" className="w-8 h-8 object-contain" />
          </div>
          <div>
            <div className="flex items-center space-x-1.5">
              <span className="font-black text-lg text-black tracking-tight leading-none">PLUTO</span>
              <span className="px-1.5 py-0.5 rounded bg-[#67E8F9] text-black border border-black text-[10px] font-black uppercase shadow-[1px_1px_0px_0px_#000]">
                vProctor
              </span>
            </div>
            <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
              AI Video Interview & Proctoring
            </p>
          </div>
        </div>

        {/* Step Progression Pills */}
        <nav className="hidden md:flex items-center space-x-1 font-mono text-xs font-bold">
          {steps.map((s, idx) => {
            const isCompleted = idx < currentIdx
            const isCurrent = s.id === currentStep
            return (
              <div key={s.id} className="flex items-center">
                <div
                  className={`px-3 py-1 rounded-lg border-2 border-black transition-all flex items-center space-x-1 ${
                    isCurrent
                      ? 'bg-[#FFE600] text-black font-black shadow-[2px_2px_0px_0px_#000] scale-105'
                      : isCompleted
                      ? 'bg-[#DCFCE7] text-black shadow-[1px_1px_0px_0px_#000]'
                      : 'bg-[#F4F0EA] text-slate-500 border-dashed opacity-75'
                  }`}
                >
                  {isCompleted ? (
                    <CheckCircle2 className="w-3.5 h-3.5 text-black stroke-[3]" />
                  ) : (
                    <span className="text-[11px]">{idx + 1}.</span>
                  )}
                  <span className="uppercase text-[11px]">{s.label.split('. ')[1] || s.label}</span>
                </div>
                {idx < steps.length - 1 && (
                  <ChevronRight className="w-3.5 h-3.5 text-slate-400 mx-0.5" />
                )}
              </div>
            )
          })}
        </nav>

        {/* Right Actions */}
        <div className="flex items-center space-x-2">
          {/* Preset Badge */}
          <div
            onClick={onOpenSettings}
            className="hidden sm:flex items-center space-x-1 px-2.5 py-1 rounded-lg bg-[#F4F0EA] hover:bg-[#FFE600] border-2 border-black text-[11px] font-black text-black cursor-pointer shadow-[2px_2px_0px_0px_#000] transition-colors"
            title="Active Proctoring Strictness Preset"
          >
            <ShieldCheck className="w-3.5 h-3.5 stroke-[2.5]" />
            <span className="uppercase">{activePreset}</span>
          </div>

          {/* Past Sessions History */}
          <button
            onClick={onOpenDashboard}
            className="p-2 rounded-xl bg-white hover:bg-[#FFE600] border-2 border-black text-black shadow-[2px_2px_0px_0px_#000] hover:-translate-y-0.5 transition-all flex items-center space-x-1 text-xs font-black uppercase"
            title="Past Sessions Dashboard"
          >
            <History className="w-4 h-4 stroke-[2.5]" />
            <span className="hidden lg:inline text-[11px]">History</span>
          </button>

          {/* Settings Trigger */}
          <button
            onClick={onOpenSettings}
            className="p-2 rounded-xl bg-white hover:bg-[#FFE600] border-2 border-black text-black shadow-[2px_2px_0px_0px_#000] hover:-translate-y-0.5 transition-all"
            title="Proctoring & Model Settings"
          >
            <Sliders className="w-4 h-4 stroke-[2.5]" />
          </button>
        </div>
      </div>
    </header>
  )
}

