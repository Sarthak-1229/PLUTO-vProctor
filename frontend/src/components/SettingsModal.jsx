import React from 'react'
import { Sliders, X, ShieldCheck, Check } from 'lucide-react'

export function SettingsModal({
  isOpen,
  onClose,
  activePreset,
  onSelectPreset,
}) {
  if (!isOpen) return null

  const presets = [
    {
      id: 'strict',
      name: 'Strict (High Stakes)',
      description: 'Alerts at 0.8s, logs penalty at 1.0s look-away. Strict yaw/pitch thresholds (±18°). Ideal for formal evaluations.',
      color: 'bg-[#FECDD3]',
    },
    {
      id: 'normal',
      name: 'Normal (Standard)',
      description: 'Alerts at 1.2s, logs penalty at 1.5s. Standard natural glance leeway (±24°). Recommended for standard interviews.',
      color: 'bg-[#FEF08A]',
    },
    {
      id: 'relaxed',
      name: 'Relaxed (Practice)',
      description: 'Alerts at 1.8s, logs penalty at 2.2s. Wide tolerance margins (±30°). Designed for candidate mock practice.',
      color: 'bg-[#DCFCE7]',
    },
  ]

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="bg-white border-[3px] border-black rounded-2xl w-full max-w-lg p-6 sm:p-8 shadow-[8px_8px_0px_0px_#000] space-y-6">
        <div className="flex items-center justify-between border-b-2 border-black pb-3">
          <div className="flex items-center space-x-2 text-black font-black uppercase text-lg">
            <Sliders className="w-5 h-5 stroke-[2.5]" />
            <span>Proctoring Sensitivity Presets</span>
          </div>
          <button
            onClick={onClose}
            className="p-1 hover:bg-slate-200 rounded-lg text-black transition-colors"
          >
            <X className="w-5 h-5 stroke-[2.5]" />
          </button>
        </div>

        <div className="space-y-3">
          <p className="text-xs font-bold text-slate-600">
            Select the proctoring sensitivity profile. All thresholds are configured through declarative JSON schema (`backend/app/config/gaze.json`).
          </p>

          <div className="space-y-3 pt-2">
            {presets.map((p) => {
              const isSelected = activePreset.toLowerCase() === p.id
              return (
                <div
                  key={p.id}
                  onClick={() => onSelectPreset(p.id)}
                  className={`p-4 rounded-xl border-2 border-black cursor-pointer transition-all ${
                    isSelected
                      ? `${p.color} shadow-[4px_4px_0px_0px_#000] -translate-y-0.5`
                      : 'bg-[#F4F0EA] hover:bg-white shadow-[2px_2px_0px_0px_#000]'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-black text-sm text-black uppercase flex items-center space-x-1.5">
                      <span>{p.name}</span>
                      {isSelected && <Check className="w-4 h-4 stroke-[3]" />}
                    </span>
                    <span className="font-mono text-[10px] font-black uppercase bg-black text-white px-2 py-0.5 rounded">
                      {p.id}
                    </span>
                  </div>
                  <p className="text-xs font-semibold text-slate-700 mt-1">{p.description}</p>
                </div>
              )
            })}
          </div>
        </div>

        <div className="pt-2 flex justify-end">
          <button
            onClick={onClose}
            className="px-6 py-2.5 rounded-xl bg-[#FFE600] hover:bg-[#ffdf00] border-2 border-black font-black text-black text-xs uppercase shadow-[3px_3px_0px_0px_#000]"
          >
            Save & Close
          </button>
        </div>
      </div>
    </div>
  )
}

