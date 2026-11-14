import React from 'react'
import {
  ShieldCheck,
  Sliders,
  History,
  CheckCircle2,
  ChevronRight,
  User,
  FileText,
  Compass,
  Shield,
  LogOut,
  LogIn,
  Video,
  TrendingUp,
} from 'lucide-react'
import plutoLogo from '../assets/logo.png'

export function Navbar({
  steps,
  currentStep,
  onStepClick,
  activePreset,
  onOpenSettings,
  onOpenDashboard,
  currentUser,
  authEnabled,
  currentPath = '/',
  onNavigate,
  onLogout,
}) {
  const currentIdx = steps.findIndex((s) => s.id === currentStep)
  const isAdmin = currentUser?.role === 'admin' || currentUser?.role === 'super_admin'
  const showSettingsTrigger = !authEnabled || isAdmin

  return (
    <header className="border-b-[3px] border-black bg-white sticky top-0 z-40 shadow-[0_4px_0_0_#000]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-3">
        {/* Brand */}
        <div
          className="flex items-center space-x-3 cursor-pointer shrink-0"
          onClick={() => {
            if (onNavigate) onNavigate('/')
            if (onStepClick) onStepClick('select')
          }}
        >
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

        {/* Step Progression Pills when in practice route */}
        {currentPath === '/' ? (
          <nav className="hidden xl:flex items-center space-x-1 font-mono text-xs font-bold">
            {steps.map((s, idx) => {
              const isCompleted = idx < currentIdx
              const isCurrent = s.id === currentStep
              return (
                <div key={s.id} className="flex items-center">
                  <div
                    className={`px-2.5 py-1 rounded-lg border-2 border-black transition-all flex items-center space-x-1 ${
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
        ) : (
          <div className="hidden md:flex items-center space-x-2">
            <button
              type="button"
              onClick={() => onNavigate && onNavigate('/')}
              className="px-3 py-1.5 rounded-xl bg-[#F4F0EA] hover:bg-[#FFE600] border-2 border-black text-xs font-black uppercase"
            >
              Mock Interview Studio
            </button>
          </div>
        )}

        {/* Right Navigation & Auth Actions */}
        <div className="flex items-center space-x-1.5 sm:space-x-2 shrink-0">
          {currentUser && onNavigate && (
            <>
              <button
                type="button"
                onClick={() => onNavigate('/rooms/join')}
                className={`px-2.5 py-1.5 rounded-xl border-2 border-black text-xs font-black uppercase flex items-center space-x-1 ${
                  currentPath === '/rooms/join' ? 'bg-[#FFE600]' : 'bg-white hover:bg-[#FFE600]'
                }`}
                title="Join Hosted Room"
              >
                <Video className="w-3.5 h-3.5" />
                <span className="hidden md:inline text-[11px]">Join Room</span>
              </button>
              <button
                type="button"
                onClick={() => onNavigate('/profile')}
                className={`px-2.5 py-1.5 rounded-xl border-2 border-black text-xs font-black uppercase flex items-center space-x-1 ${
                  currentPath === '/profile' ? 'bg-[#FFE600]' : 'bg-white hover:bg-[#FFE600]'
                }`}
                title="Candidate Profile"
              >
                <User className="w-3.5 h-3.5" />
                <span className="hidden md:inline text-[11px]">Profile</span>
              </button>
              <button
                type="button"
                onClick={() => onNavigate('/resumes')}
                className={`px-2.5 py-1.5 rounded-xl border-2 border-black text-xs font-black uppercase flex items-center space-x-1 ${
                  currentPath === '/resumes' ? 'bg-[#FFE600]' : 'bg-white hover:bg-[#FFE600]'
                }`}
                title="Resume Library"
              >
                <FileText className="w-3.5 h-3.5" />
                <span className="hidden md:inline text-[11px]">Resumes</span>
              </button>
              <button
                type="button"
                onClick={() => onNavigate('/recommendations')}
                className={`px-2.5 py-1.5 rounded-xl border-2 border-black text-xs font-black uppercase flex items-center space-x-1 ${
                  currentPath === '/recommendations' ? 'bg-[#FFE600]' : 'bg-white hover:bg-[#FFE600]'
                }`}
                title="Job Recommendations"
              >
                <Compass className="w-3.5 h-3.5" />
                <span className="hidden lg:inline text-[11px]">Jobs</span>
              </button>
              <button
                type="button"
                onClick={() => onNavigate('/roadmap')}
                className={`px-2.5 py-1.5 rounded-xl border-2 border-black text-xs font-black uppercase flex items-center space-x-1 ${
                  currentPath === '/roadmap' ? 'bg-[#FFE600]' : 'bg-white hover:bg-[#FFE600]'
                }`}
                title="Learning Roadmap"
              >
                <TrendingUp className="w-3.5 h-3.5" />
                <span className="hidden lg:inline text-[11px]">Roadmap</span>
              </button>
            </>
          )}

          {isAdmin && onNavigate && (
            <button
              type="button"
              onClick={() => onNavigate('/admin')}
              className={`px-2.5 py-1.5 rounded-xl border-2 border-black text-xs font-black uppercase flex items-center space-x-1 ${
                currentPath === '/admin' ? 'bg-[#FECDD3]' : 'bg-white hover:bg-[#FECDD3]'
              }`}
              title="Admin Console"
            >
              <Shield className="w-3.5 h-3.5" />
              <span className="hidden md:inline text-[11px]">Admin</span>
            </button>
          )}

          {showSettingsTrigger && (
            <div
              onClick={onOpenSettings}
              className="hidden sm:flex items-center space-x-1 px-2.5 py-1.5 rounded-xl bg-[#F4F0EA] hover:bg-[#FFE600] border-2 border-black text-[11px] font-black text-black cursor-pointer shadow-[2px_2px_0px_0px_#000] transition-colors"
              title="Active Proctoring Strictness Preset"
            >
              <ShieldCheck className="w-3.5 h-3.5 stroke-[2.5]" />
              <span className="uppercase">{activePreset}</span>
            </div>
          )}

          <button
            type="button"
            onClick={onOpenDashboard}
            className="p-2 rounded-xl bg-white hover:bg-[#FFE600] border-2 border-black text-black shadow-[2px_2px_0px_0px_#000] transition-all flex items-center space-x-1 text-xs font-black uppercase"
            title="Interview History"
          >
            <History className="w-4 h-4 stroke-[2.5]" />
            <span className="hidden xl:inline text-[11px]">History</span>
          </button>

          {showSettingsTrigger && (
            <button
              type="button"
              onClick={onOpenSettings}
              className="p-2 rounded-xl bg-white hover:bg-[#FFE600] border-2 border-black text-black shadow-[2px_2px_0px_0px_#000] transition-all"
              title="Proctoring & Model Settings"
            >
              <Sliders className="w-4 h-4 stroke-[2.5]" />
            </button>
          )}

          {currentUser ? (
            <button
              type="button"
              onClick={onLogout}
              className="px-2.5 py-1.5 rounded-xl bg-[#F4F0EA] hover:bg-[#FEE2E2] border-2 border-black text-xs font-black uppercase flex items-center space-x-1"
              title={`Signed in as ${currentUser.email}`}
            >
              <LogOut className="w-3.5 h-3.5" />
              <span className="hidden sm:inline text-[11px]">Sign Out</span>
            </button>
          ) : (
            onNavigate && (
              <button
                type="button"
                onClick={() => onNavigate('/login')}
                className="px-2.5 py-1.5 rounded-xl bg-[#FFE600] border-2 border-black text-xs font-black uppercase flex items-center space-x-1 shadow-[2px_2px_0px_0px_#000]"
              >
                <LogIn className="w-3.5 h-3.5" />
                <span className="text-[11px]">Sign In</span>
              </button>
            )
          )}
        </div>
      </div>
    </header>
  )
}
