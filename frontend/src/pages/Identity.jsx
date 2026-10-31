import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, ArrowRight, Camera, Check, Clock3, LoaderCircle, RefreshCw, ShieldCheck, Upload, Video } from 'lucide-react'
import { Card } from '../components/common/Card'
import { Button } from '../components/common/Button'
import { StatusBadge } from '../components/common/StatusBadge'
import { Feedback } from '../components/common/Feedback'
import { apiMessage } from '../services/api/client'
import {
  analyzeDocument,
  assessFaceMatch,
  documentStatus,
  identityStatus,
  issueLivenessChallenge,
  submitLiveness,
  submitSelfie,
  uploadDocument,
} from '../services/api/identity'
import {
  listInstitutions,
  myInstitutionSelection,
  saveInstitutionSelection,
} from '../services/api/institutions'
import { useAuth } from '../context/AuthContext'

const STEPS = [
  'Institution information',
  'Identity document',
  'Selfie capture',
  'Liveness',
  'Final identity status',
]
const MAX_DOCUMENT_BYTES = 5 * 1024 * 1024
const MAX_SELFIE_BYTES = 2 * 1024 * 1024
const MAX_LIVENESS_BYTES = 10 * 1024 * 1024
const DOCUMENT_FORMATS = {
  '.pdf': 'application/pdf',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.png': 'image/png',
}
const STATUS_LABELS = {
  APPROVED: 'Verified',
  VERIFIED: 'Verified',
  LIVE: 'Live confirmed',
  MATCH: 'Match confirmed',
  NO_MATCH: 'No match',
  COMPLETED: 'Completed',
  SUBMITTED: 'Submitted',
  PENDING: 'Pending',
  PROCESSING: 'Processing',
  FLAGGED: 'Review required',
  CHALLENGE_ISSUED: 'Challenge issued',
  REVIEW_REQUIRED: 'Review required',
  RETRY_REQUIRED: 'Retry required',
  PROVIDER_UNAVAILABLE: 'Provider unavailable',
  UNAVAILABLE: 'Unavailable',
  REGISTERED: 'Registered',
  SELECTED: 'Selected',
  NOT_SELECTED: 'Not selected',
  NOT_STARTED: 'Not started',
  NOT_SUBMITTED: 'Not submitted',
  NOT_VERIFIED: 'Not verified',
  DEMO_CONFIRMED: 'Demo confirmed (not verified)',
  UNVERIFIED: 'Not verified',
  FAILED: 'Failed',
  REJECTED: 'Rejected',
  ENROLLMENT_CONFIRMED: 'Verified',
  ENROLLMENT_PENDING: 'Pending',
  ENROLLMENT_REJECTED: 'Not verified',
}

function statusLabel(value, fallback = 'Not started') {
  if (!value) return fallback
  const normalized = String(value).toUpperCase()
  return STATUS_LABELS[normalized] || normalized.toLowerCase().replaceAll('_', ' ')
}

function isDocumentAnalysisComplete(result) {
  return Boolean(
    result?.analysis_completed_at
    && ['COMPLETED', 'FLAGGED'].includes(String(result.status || '').toUpperCase()),
  )
}

function getStepValue(key) {
  const saved = Number(sessionStorage.getItem(key))
  return Number.isInteger(saved) && saved >= 1 && saved <= STEPS.length ? saved : 1
}

function getStoredObject(key) {
  try {
    const saved = sessionStorage.getItem(key)
    return saved ? JSON.parse(saved) : null
  } catch {
    sessionStorage.removeItem(key)
    return null
  }
}

function getFileExtension(fileName) {
  return fileName.slice(fileName.lastIndexOf('.')).toLowerCase()
}

function captureJpeg(video) {
  return new Promise((resolve, reject) => {
    const sourceWidth = video.videoWidth
    const sourceHeight = video.videoHeight
    if (!sourceWidth || !sourceHeight) {
      reject(new Error('Camera preview is not ready yet. Wait for the video to appear and try again.'))
      return
    }

    const scale = Math.min(1, 1280 / Math.max(sourceWidth, sourceHeight))
    const canvas = document.createElement('canvas')
    canvas.width = Math.round(sourceWidth * scale)
    canvas.height = Math.round(sourceHeight * scale)
    const context = canvas.getContext('2d')
    if (!context) {
      reject(new Error('Could not prepare the captured image. Please try again.'))
      return
    }
    context.drawImage(video, 0, 0, canvas.width, canvas.height)

    const qualities = [0.85, 0.7, 0.55]
    const encode = (index) => {
      canvas.toBlob((blob) => {
        if (!blob) {
          reject(new Error('Could not capture an image from the camera.'))
          return
        }
        if (blob.size <= MAX_SELFIE_BYTES) {
          resolve(blob)
          return
        }
        if (index + 1 < qualities.length) {
          encode(index + 1)
          return
        }
        reject(new Error('The captured selfie is larger than the 2 MB upload limit. Please try again in better lighting.'))
      }, 'image/jpeg', qualities[index])
    }
    encode(0)
  })
}

function chooseRecordingMimeType() {
  if (!window.MediaRecorder) return ''
  const candidates = ['video/webm;codecs=vp8,opus', 'video/webm', 'video/mp4']
  return candidates.find((candidate) => MediaRecorder.isTypeSupported(candidate)) || ''
}

export function Identity() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const storagePrefix = `unipass_identity_${user?.id || 'session'}`
  const keys = useMemo(() => ({
    step: `${storagePrefix}_step`,
    verification: `${storagePrefix}_verification`,
    challenge: `${storagePrefix}_challenge`,
    demoEmail: `${storagePrefix}_demo_email`,
    demoEmailConfirmation: `${storagePrefix}_demo_email_confirmation`,
  }), [storagePrefix])

  const [step, setStep] = useState(1)
  const [storageReady, setStorageReady] = useState(false)
  const [status, setStatus] = useState(null)
  const [institutions, setInstitutions] = useState([])
  const [verificationId, setVerificationId] = useState('')
  const [institutionId, setInstitutionId] = useState('')
  const [savedInstitutionId, setSavedInstitutionId] = useState('')
  const [email, setEmail] = useState(user?.email || '')
  const [confirmedDemoEmail, setConfirmedDemoEmail] = useState('')
  const [documentType, setDocumentType] = useState('passport')
  const [file, setFile] = useState(null)
  const [documentAnalysisStatus, setDocumentAnalysisStatus] = useState(null)
  const [documentStatusDetails, setDocumentStatusDetails] = useState(null)
  const [selfie, setSelfie] = useState(null)
  const [selfieConsent, setSelfieConsent] = useState(false)
  const [challenge, setChallenge] = useState(null)
  const [livenessCapture, setLivenessCapture] = useState(null)
  const [livenessConsent, setLivenessConsent] = useState(false)
  const [cameraMode, setCameraMode] = useState('')
  const [cameraActive, setCameraActive] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const [recordingSize, setRecordingSize] = useState(0)
  const [uploadProgress, setUploadProgress] = useState(null)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [selfiePreview, setSelfiePreview] = useState('')
  const [now, setNow] = useState(Date.now())

  const selfieVideoRef = useRef(null)
  const livenessVideoRef = useRef(null)
  const streamRef = useRef(null)
  const mountedRef = useRef(false)
  const recorderRef = useRef(null)
  const recordingChunksRef = useRef([])
  const documentFileRef = useRef(null)

  function clearDocumentFile() {
    setFile(null)
    if (documentFileRef.current) documentFileRef.current.value = ''
  }

  function stopCamera() {
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
    setCameraActive(false)
    setCameraMode('')
    if (selfieVideoRef.current) selfieVideoRef.current.srcObject = null
    if (livenessVideoRef.current) livenessVideoRef.current.srcObject = null
  }

  async function refresh() {
    try {
      const [identityResponse, institutionsResponse, selectionResponse] = await Promise.all([
        identityStatus(),
        listInstitutions(),
        myInstitutionSelection(),
      ])
      const latestStatus = identityResponse.data
      const latestVerificationId = latestStatus.verification_id || ''
      let detailError = ''
      setStatus(latestStatus)
      setInstitutions(institutionsResponse.data)
      setVerificationId(latestVerificationId)
      setDocumentAnalysisStatus(latestStatus.document_analysis_status)

      if (latestVerificationId) {
        sessionStorage.setItem(keys.verification, latestVerificationId)
        try {
          const detailResponse = await documentStatus(latestVerificationId)
          setDocumentStatusDetails(detailResponse.data)
        } catch (err) {
          setDocumentStatusDetails(null)
          detailError = apiMessage(err)
        }
      } else {
        sessionStorage.removeItem(keys.verification)
        setDocumentStatusDetails(null)
        setDocumentAnalysisStatus(null)
      }

      const savedChallenge = getStoredObject(keys.challenge)
      if (savedChallenge?.verification_id === latestVerificationId && Date.parse(savedChallenge.expires_at) > Date.now()) {
        setChallenge(savedChallenge)
      } else {
        setChallenge(null)
        sessionStorage.removeItem(keys.challenge)
      }
      const selectedInstitutionId = selectionResponse.data.institution_id || ''
      const validInstitutionId = institutionsResponse.data.some((item) => item.id === selectedInstitutionId)
        ? selectedInstitutionId
        : ''
      setInstitutionId(validInstitutionId)
      setSavedInstitutionId(validInstitutionId)
      setError(detailError)
    } catch (err) {
      setError(apiMessage(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!user?.id) return
    setStep(getStepValue(keys.step))
    setEmail(sessionStorage.getItem(keys.demoEmail) || user.email || '')
    setConfirmedDemoEmail(sessionStorage.getItem(keys.demoEmailConfirmation) || '')
    setStorageReady(true)
    refresh()
  }, [user?.id])

  useEffect(() => {
    if (!storageReady) return
    sessionStorage.setItem(keys.step, String(step))
  }, [keys.step, step, storageReady])

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    if (!selfie) {
      setSelfiePreview('')
      return undefined
    }
    const previewUrl = URL.createObjectURL(selfie)
    setSelfiePreview(previewUrl)
    return () => URL.revokeObjectURL(previewUrl)
  }, [selfie])

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      streamRef.current?.getTracks().forEach((track) => track.stop())
      streamRef.current = null
      if (recorderRef.current?.state === 'recording') recorderRef.current.stop()
    }
  }, [])

  useEffect(() => {
    if (step === 3 && selfieVideoRef.current && cameraMode === 'selfie' && streamRef.current) {
      selfieVideoRef.current.srcObject = streamRef.current
      selfieVideoRef.current.play().catch(() => setError('Could not start the camera preview. Check browser camera permissions and try again.'))
    } else if (step === 4 && livenessVideoRef.current && cameraMode === 'liveness' && streamRef.current) {
      livenessVideoRef.current.srcObject = streamRef.current
      livenessVideoRef.current.play().catch(() => setError('Could not start the camera preview. Check browser camera permissions and try again.'))
    } else if (((step !== 3 && cameraMode === 'selfie') || (step !== 4 && cameraMode === 'liveness')) && streamRef.current) {
      if (recorderRef.current?.state === 'recording') recorderRef.current.stop()
      else stopCamera()
    }
  }, [step, cameraMode])

  async function startCamera(mode) {
    setError('')
    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error('Camera access is not supported by this browser. Use a current browser on HTTPS or localhost.')
      }
      if (streamRef.current) stopCamera()
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' }, audio: false })
      if (!mountedRef.current) {
        stream.getTracks().forEach((track) => track.stop())
        return
      }
      streamRef.current = stream
      setCameraMode(mode)
      setCameraActive(true)
    } catch (err) {
      if (mountedRef.current) {
        setError(`${err.message || 'Camera permission was denied or unavailable.'} Allow camera access for this site in your browser settings, then try again.`)
      }
    }
  }

  async function captureSelfie() {
    try {
      const blob = await captureJpeg(selfieVideoRef.current)
      setSelfie(blob)
      stopCamera()
    } catch (err) {
      setError(err.message)
    }
  }

  function startLivenessRecording() {
    setError('')
    const mimeType = chooseRecordingMimeType()
    if (!mimeType) {
      setError('This browser does not support a video format accepted by the liveness service. Use a browser that supports WebM or MP4 recording.')
      return
    }
    if (!streamRef.current || !cameraActive || cameraMode !== 'liveness') {
      setError('Start the camera before recording the liveness challenge.')
      return
    }
    if (!challenge || Date.parse(challenge.expires_at) <= Date.now()) {
      setError('The liveness challenge is missing or expired. Request a new challenge before recording.')
      return
    }

    try {
      const recorder = new MediaRecorder(streamRef.current, { mimeType })
      recordingChunksRef.current = []
      recorder.ondataavailable = (event) => {
        if (event.data.size) recordingChunksRef.current.push(event.data)
      }
      recorder.onstop = () => {
        const blob = new Blob(recordingChunksRef.current, { type: recorder.mimeType.split(';')[0] })
        recordingChunksRef.current = []
        if (blob.size > MAX_LIVENESS_BYTES) {
          setLivenessCapture(null)
          setError('The liveness recording exceeds the 10 MB limit. Record a shorter clip and try again.')
        } else if (blob.size === 0) {
          setLivenessCapture(null)
          setError('The liveness recording was empty. Please record the challenge again.')
        } else {
          setLivenessCapture(blob)
          setRecordingSize(blob.size)
        }
        recorderRef.current = null
        setIsRecording(false)
        stopCamera()
      }
      recorderRef.current = recorder
      recorder.start()
      setIsRecording(true)
    } catch (err) {
      setError(err.message || 'The browser could not start video recording.')
    }
  }

  function stopLivenessRecording() {
    if (recorderRef.current?.state === 'recording') recorderRef.current.stop()
  }

  async function perform(action) {
    setBusy(true)
    setError('')
    setMessage('')
    setUploadProgress(null)
    try {
      await action()
    } catch (err) {
      setError(apiMessage(err))
    } finally {
      setBusy(false)
      setUploadProgress(null)
    }
  }

  async function saveSelectedInstitution() {
    if (!institutions.some((item) => item.id === institutionId)) {
      setError('Select an institution from the loaded list before continuing.')
      return
    }
    await perform(async () => {
      const response = await saveInstitutionSelection(institutionId)
      setInstitutionId(response.data.institution_id)
      setSavedInstitutionId(response.data.institution_id)
      setMessage('Institution selection saved successfully.')
    })
  }

  async function handleInstitutionNext() {
    if (!emailIsValid) {
      setError('Please enter a valid email address.')
      return
    }
    if (!demoIsConfirmed) {
      setError('Please confirm the demo email step.')
      return
    }
    if (
      !institutions.some((item) => item.id === institutionId)
      || savedInstitutionId !== institutionId
    ) {
      setError('Please select and save an institution.')
      return
    }
    setError('')
    setStep(2)
  }

  function updateDemoEmail(value) {
    setEmail(value)
    setConfirmedDemoEmail('')
    sessionStorage.setItem(keys.demoEmail, value)
    sessionStorage.removeItem(keys.demoEmailConfirmation)
    setError('')
    setMessage('')
  }

  function confirmEmailForDemo() {
    if (!emailIsValid) {
      setError('Please enter a valid email address.')
      return
    }
    const normalizedEmail = email.trim().toLowerCase()
    sessionStorage.setItem(keys.demoEmail, email)
    sessionStorage.setItem(keys.demoEmailConfirmation, normalizedEmail)
    setConfirmedDemoEmail(normalizedEmail)
    setError('')
    setMessage('Demo confirmation successful. No email was sent; email ownership has not been verified.')
  }

  function validateDocumentFile(selectedFile) {
    if (!selectedFile) return 'Choose a document file before continuing.'
    const extension = getFileExtension(selectedFile.name)
    if (!Object.hasOwn(DOCUMENT_FORMATS, extension) || selectedFile.type !== DOCUMENT_FORMATS[extension]) {
      return 'Choose a PDF, JPEG, or PNG file with a matching file type.'
    }
    if (selectedFile.size <= 0 || selectedFile.size > MAX_DOCUMENT_BYTES) {
      return 'The document must be smaller than or equal to 5 MB.'
    }
    return ''
  }

  async function uploadAndAnalyzeDocument() {
    const validationError = validateDocumentFile(file)
    if (validationError) {
      setError(validationError)
      return
    }
    setBusy(true)
    setError('')
    setMessage('')
    setUploadProgress({ label: 'Uploading document', value: 0 })
    let uploadedVerificationId = ''
    try {
      const uploadResponse = await uploadDocument(documentType, file, demoIsConfirmed, (event) => {
        if (event.total) setUploadProgress({ label: 'Uploading document', value: Math.round(event.loaded * 100 / event.total) })
      })
      uploadedVerificationId = uploadResponse.data.id
      setVerificationId(uploadedVerificationId)
      sessionStorage.setItem(keys.verification, uploadedVerificationId)
      setDocumentStatusDetails(uploadResponse.data)
      setDocumentAnalysisStatus(uploadResponse.data.status)
      clearDocumentFile()
      setMessage(`Document uploaded. Initial backend status: ${statusLabel(uploadResponse.data.status)}.`)
      await refresh()
      try {
        setDocumentAnalysisStatus('PROCESSING')
        const analysisResponse = await analyzeDocument(uploadedVerificationId)
        setDocumentAnalysisStatus(analysisResponse.data.status)
        setDocumentStatusDetails((current) => ({ ...current, ...analysisResponse.data }))
        setMessage(`Document analysis status returned by the backend: ${statusLabel(analysisResponse.data.status)}.`)
        await refresh()
        if (isDocumentAnalysisComplete(analysisResponse.data)) setStep(3)
      } catch (analysisError) {
        await refresh()
        setError(`Document uploaded successfully, but analysis could not be completed: ${apiMessage(analysisError)}`)
      }
    } catch (uploadError) {
      setError(apiMessage(uploadError))
    } finally {
      setBusy(false)
      setUploadProgress(null)
    }
  }

  async function retryDocumentAnalysis() {
    if (!verificationId) return
    await perform(async () => {
      setDocumentAnalysisStatus('PROCESSING')
      try {
        const response = await analyzeDocument(verificationId)
        setDocumentAnalysisStatus(response.data.status)
        setDocumentStatusDetails((current) => ({ ...current, ...response.data }))
        await refresh()
        setMessage(`Document analysis status returned by the backend: ${statusLabel(response.data.status)}.`)
      } catch (analysisError) {
        await refresh()
        throw analysisError
      }
    })
  }

  async function uploadSelfieAndContinue() {
    if (status?.selfie_status === 'SUBMITTED') {
      setStep(4)
      return
    }
    if (!verificationId) {
      setError('Upload an identity document before submitting a selfie.')
      return
    }
    if (!selfieConsent) {
      setError('Consent is required before uploading the selfie.')
      return
    }
    if (!selfie || selfie.type !== 'image/jpeg' || selfie.size <= 0 || selfie.size > MAX_SELFIE_BYTES) {
      setError('Capture a JPEG selfie smaller than or equal to 2 MB before continuing.')
      return
    }

    await perform(async () => {
      const response = await submitSelfie(verificationId, selfie, (event) => {
        if (event.total) setUploadProgress({ label: 'Uploading selfie', value: Math.round(event.loaded * 100 / event.total) })
      })
      setSelfie(null)
      await refresh()
      let faceAssessment = null
      if (documentStatusDetails?.portrait_available) {
        try {
          faceAssessment = (await assessFaceMatch(verificationId)).data
        } catch (matchError) {
          setError(`Selfie uploaded, but face matching could not be completed: ${apiMessage(matchError)}`)
        }
      }
      await refresh()
      const faceStatus = faceAssessment?.status || status?.face_match_status || 'NOT_STARTED'
      const faceNote = documentStatusDetails?.portrait_available
        ? ` Face match status: ${statusLabel(faceStatus)}.`
        : ' Face matching was not attempted because document portrait extraction is unavailable.'
      if (!error) setMessage(`Selfie status returned by the backend: ${statusLabel(response.data.selfie_status)}.${faceNote}`)
      setStep(4)
    })
  }

  async function requestChallenge() {
    if (!verificationId) {
      setError('Upload an identity document before requesting a liveness challenge.')
      return
    }
    await perform(async () => {
      const response = await issueLivenessChallenge(verificationId)
      const challengeData = {
        ...response.data,
        expires_at: new Date(response.data.expires_at).toISOString(),
      }
      setLivenessCapture(null)
      setRecordingSize(0)
      setChallenge(challengeData)
      sessionStorage.setItem(keys.challenge, JSON.stringify(challengeData))
      setMessage(`Challenge issued. Backend status: ${statusLabel(response.data.liveness_status)}. This is not a liveness result.`)
      await refresh()
      setChallenge(challengeData)
    })
  }

  async function submitLivenessCapture() {
    if (!verificationId || !challenge) {
      setError('Request an active liveness challenge before submitting a recording.')
      return
    }
    if (Date.parse(challenge.expires_at) <= Date.now()) {
      setError('The liveness challenge has expired. Request a new challenge before submitting.')
      setChallenge(null)
      setLivenessCapture(null)
      setRecordingSize(0)
      sessionStorage.removeItem(keys.challenge)
      return
    }
    if (!livenessConsent) {
      setError('Consent is required before submitting a liveness recording.')
      return
    }
    if (!livenessCapture || !['video/webm', 'video/mp4', 'video/quicktime'].includes(livenessCapture.type.split(';')[0]) || livenessCapture.size > MAX_LIVENESS_BYTES) {
      setError('Record a supported WebM or MP4 video no larger than 10 MB.')
      return
    }

    await perform(async () => {
      const response = await submitLiveness(verificationId, challenge.challenge_id, livenessCapture, (event) => {
        if (event.total) setUploadProgress({ label: 'Submitting liveness capture', value: Math.round(event.loaded * 100 / event.total) })
      })
      setLivenessCapture(null)
      setChallenge(null)
      sessionStorage.removeItem(keys.challenge)
      await refresh()
      setMessage(`Liveness status returned by the backend: ${statusLabel(response.data.liveness_status)}. No provider-generated success is implied.`)
    })
  }

  function goBack() {
    if (step > 1) setStep((current) => current - 1)
  }

  function continueToFinalStatus() {
    stopCamera()
    setStep(5)
    refresh()
  }

  const selectedInstitution = institutions.find((institution) => institution.id === institutionId)
  const normalizedEmail = email.trim().toLowerCase()
  const demoIsConfirmed = Boolean(
    normalizedEmail
    && confirmedDemoEmail
    && normalizedEmail === confirmedDemoEmail.toLowerCase(),
  )
  const emailStatus = demoIsConfirmed ? 'DEMO_CONFIRMED' : 'NOT_VERIFIED'
  const emailIsValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())
  const backendBlocksUnverifiedEmail = Boolean(status?.email_ownership_required)
  const documentStepComplete = Boolean(
    verificationId
    && documentStatusDetails?.analysis_completed_at
    && ['COMPLETED', 'FLAGGED'].includes(String(documentStatusDetails?.status || '').toUpperCase()),
  )
  const currentDocumentAnalysisStatus = (
    documentAnalysisStatus
    || documentStatusDetails?.status
    || status?.document_analysis_status
  )
  const enrollmentStatus = 'NOT_VERIFIED'
  const missingStatus = status ? 'NOT_STARTED' : error ? 'UNAVAILABLE' : 'NOT_STARTED'
  const challengeExpired = Boolean(challenge && Date.parse(challenge.expires_at) <= now)
  const progressPercent = Math.round(((step - 1) / (STEPS.length - 1)) * 100)

  return (
    <main className="mx-auto max-w-4xl px-4 py-8 sm:px-6 sm:py-10">
      <header>
        <p className="text-sm font-bold uppercase tracking-[.16em] text-signal">UniPass identity verification</p>
        <div className="mt-2 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-ink sm:text-4xl">{STEPS[step - 1]}</h1>
            <p className="mt-2 text-sm text-slate-500">Step {step} of {STEPS.length} · {progressPercent}% complete</p>
          </div>
          <Button variant="secondary" onClick={() => perform(refresh)} disabled={busy || loading}>
            {loading ? <LoaderCircle size={16} className="mr-2 inline animate-spin" /> : <RefreshCw size={16} className="mr-2 inline" />}
            Refresh status
          </Button>
        </div>
      </header>

      <nav className="mt-7" aria-label="Identity verification progress">
        <ol className="grid grid-cols-5 gap-2">
          {STEPS.map((title, index) => {
            const number = index + 1
            const isCurrent = number === step
            const isComplete = number < step
            return (
              <li key={title}>
                <div
                  role="group"
                  aria-current={isCurrent ? 'step' : undefined}
                  aria-label={`Step ${number}: ${title}${isComplete ? ', previous step' : isCurrent ? ', current step' : ', upcoming step'}`}
                  className={`flex min-h-11 items-center gap-2 border-t-4 pt-2 ${isCurrent ? 'border-signal' : isComplete ? 'border-emerald-500' : 'border-slate-200'}`}
                >
                  <span className={`grid h-7 w-7 shrink-0 place-items-center rounded-full text-xs font-bold ${isCurrent ? 'bg-signal text-white' : isComplete ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>
                    {isComplete ? <Check size={14} /> : number}
                  </span>
                  <span className="hidden text-xs font-semibold text-slate-600 sm:inline">{title}</span>
                </div>
              </li>
            )
          })}
        </ol>
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100" role="progressbar" aria-valuenow={progressPercent} aria-valuemin={0} aria-valuemax={100} aria-label={`Wizard progress: ${progressPercent}%`}>
          <div className="h-full rounded-full bg-signal transition-all" style={{ width: `${progressPercent}%` }} />
        </div>
      </nav>

      <div className="mt-6" aria-live="polite">
        <Feedback error={error} message={message} />
      </div>

      <Card className="mt-6">
        {loading ? (
          <div className="flex min-h-48 items-center justify-center gap-3 text-slate-500" role="status">
            <LoaderCircle className="animate-spin" size={20} />Loading your current verification status…
          </div>
        ) : (
          <>
            <div className="min-h-72">
              {step === 1 && (
                <section aria-labelledby="institution-heading">
                  <p className="text-xs font-bold uppercase tracking-[.14em] text-amber-700">DEMO MODE - EMAIL DELIVERY DISABLED</p>
                  <h2 id="institution-heading" className="text-xl font-bold text-ink">Email and institution</h2>
                  <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">Enter a valid personal or institutional email. This demonstration does not send email or verify ownership, and institution selection does not verify student enrollment.</p>
                  <label className="mt-6 block text-sm font-semibold text-ink" htmlFor="identity-email">
                    Email address <span aria-hidden="true" className="text-red-600">*</span>
                  </label>
                  <input
                    id="identity-email"
                    type="email"
                    required
                    value={email}
                    onChange={(event) => updateDemoEmail(event.target.value)}
                    autoComplete="email"
                    className="mt-2 w-full rounded-xl border border-slate-200 px-3 py-3"
                    aria-describedby="email-demo-note"
                  />
                  <div className="mt-3 flex flex-wrap items-center gap-3">
                    <StatusBadge
                      value={emailStatus}
                      label={statusLabel(emailStatus)}
                    />
                    <Button type="button" variant="secondary" onClick={confirmEmailForDemo} disabled={busy}>
                      Confirm for demo
                    </Button>
                  </div>
                  <p id="email-demo-note" className="mt-3 text-sm leading-6 text-slate-600">
                    {demoIsConfirmed
                      ? 'DEMO_CONFIRMED. No email was sent; email ownership has not been verified.'
                      : 'Email state is NOT_VERIFIED until you confirm this demo step. Demo confirmation is local to this browser session.'}
                  </p>
                  <label className="mt-6 block text-sm font-semibold text-ink" htmlFor="institution-select">Institution <span aria-hidden="true" className="text-red-600">*</span></label>
                  <select
                    id="institution-select"
                    required
                    value={institutionId}
                    onChange={(event) => setInstitutionId(event.target.value)}
                    className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-3"
                    aria-describedby="institution-note"
                  >
                    <option value="">Select an institution</option>
                    {institutions.map((institution) => (
                      <option key={institution.id} value={institution.id}>{institution.official_display_name}</option>
                    ))}
                  </select>
                  {!institutions.some((institution) => institution.official_display_name === 'Anna University, BIT Campus, Tiruchirappalli') && (
                    <p className="mt-2 text-sm text-amber-700" role="status">Anna University, BIT Campus, Tiruchirappalli is not currently returned by the backend. No institution record has been created or fabricated.</p>
                  )}
                  <Button type="button" className="mt-4" variant="secondary" onClick={saveSelectedInstitution} disabled={busy || !institutionId}>
                    Save Institution Selection
                  </Button>
                  <p className="mt-4 rounded-xl bg-amber-50 p-4 text-sm leading-6 text-amber-900">
                    Your selection is saved to your authenticated account. Selection is not enrollment; enrollment remains unverified until an authoritative institution source is connected.
                  </p>
                </section>
              )}

              {step === 2 && (
                <section aria-labelledby="document-heading">
                  <h2 id="document-heading" className="text-xl font-bold text-ink">Identity document</h2>
                  <p className="mt-2 text-sm leading-6 text-slate-600">Supported formats are PDF, JPEG, and PNG. Maximum size: 5 MB. The backend validates file contents and analysis status.</p>
                  {status?.identity_demo_mode && (
                    <p className="mt-3 rounded-xl bg-amber-50 p-4 text-sm leading-6 text-amber-900">
                      Demo mode: email ownership has not been verified. This designated synthetic account may upload after completing the demo email-confirmation step. Uploads remain pending/reviewable and do not verify enrollment or identity.
                    </p>
                  )}
                  {backendBlocksUnverifiedEmail && (
                    <p className="mt-3 rounded-xl bg-amber-50 p-4 text-sm leading-6 text-amber-900">
                      Verify email ownership before continuing identity verification. The backend requires genuine email verification for this account.
                    </p>
                  )}
                  {verificationId && (
                    <div className="mt-5 rounded-2xl border border-slate-200 bg-mist p-4">
                      <p className="font-semibold text-ink">Current document response</p>
                      <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                        <StatusRow label="Document type" value={documentStatusDetails?.document_type || documentType} />
                        <StatusRow label="Email verification bypass" value={documentStatusDetails?.email_verification_bypassed ? 'DEMO_BYPASS_RECORDED' : 'NOT_USED'} />
                        <StatusRow label="Extracted document type" value={documentStatusDetails?.extracted_document_type || 'NOT_STARTED'} />
                        <StatusRow label="Analysis status" value={currentDocumentAnalysisStatus || 'NOT_STARTED'} />
                        <StatusRow label="Analysis source" value={documentStatusDetails?.analysis_source || documentStatusDetails?.source || 'NOT_STARTED'} />
                        <StatusRow label="Portrait extracted" value={documentStatusDetails?.portrait_available ? 'AVAILABLE' : 'UNAVAILABLE'} />
                      </dl>
                      {(documentStatusDetails?.analysis_reason_code || documentStatusDetails?.reason_code) && (
                        <p className="mt-3 break-all text-xs text-slate-600">
                          Backend reason: {documentStatusDetails.analysis_reason_code || documentStatusDetails.reason_code}
                        </p>
                      )}
                      <p className="mt-3 text-xs leading-5 text-slate-600">Retry required, review required, and failed results are not successful verification. Portrait extraction is unavailable unless the backend returns it.</p>
                    </div>
                  )}
                  <label className="mt-6 block text-sm font-semibold text-ink" htmlFor="document-type">Document type</label>
                  <select id="document-type" value={documentType} onChange={(event) => setDocumentType(event.target.value)} className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-3">
                    <option value="passport">Passport</option>
                    <option value="national_id">National ID</option>
                  </select>
                  <input
                    ref={documentFileRef}
                    id="document-file"
                    type="file"
                    accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
                    onChange={(event) => setFile(event.target.files?.[0] || null)}
                    className="sr-only"
                  />
                  <div className="mt-5 flex flex-wrap gap-2">
                    <Button variant="secondary" onClick={() => documentFileRef.current?.click()} disabled={busy}>
                      Choose Document
                    </Button>
                    <Button onClick={uploadAndAnalyzeDocument} disabled={busy || !file}>
                      {busy ? <LoaderCircle size={16} className="mr-2 inline animate-spin" /> : <Upload size={16} className="mr-2 inline" />}
                      Upload and Analyze
                    </Button>
                    {file && (
                      <Button variant="secondary" onClick={clearDocumentFile} disabled={busy}>Replace selected file</Button>
                    )}
                  </div>
                  {file && (
                    <p className="mt-3 break-all rounded-xl bg-mist p-3 text-sm text-slate-700">
                      Selected: {file.name} · {(file.size / (1024 * 1024)).toFixed(2)} MB
                    </p>
                  )}
                  {uploadProgress && <UploadProgress label={uploadProgress.label} value={uploadProgress.value} />}
                  {verificationId && ['PENDING', 'RETRY_REQUIRED', 'FAILED'].includes(String(currentDocumentAnalysisStatus || '').toUpperCase()) && (
                    <Button className="mt-4" variant="secondary" onClick={retryDocumentAnalysis} disabled={busy}>
                      {busy ? <LoaderCircle size={16} className="mr-2 inline animate-spin" /> : <RefreshCw size={16} className="mr-2 inline" />}
                      Retry document analysis
                    </Button>
                  )}
                  {verificationId && ['PROCESSING', 'RETRY_REQUIRED', 'FAILED'].includes(String(currentDocumentAnalysisStatus || '').toUpperCase()) && (
                    <p className="mt-3 text-sm leading-6 text-slate-600" role="status">
                      Backend analysis status: {statusLabel(currentDocumentAnalysisStatus)}. The next step stays unavailable until analysis is completed or flagged for review.
                    </p>
                  )}
                </section>
              )}

              {step === 3 && (
                <section aria-labelledby="selfie-heading">
                  <h2 id="selfie-heading" className="text-xl font-bold text-ink">Selfie capture</h2>
                  <p className="mt-2 text-sm leading-6 text-slate-600">Use the camera to capture a JPEG selfie. The backend accepts images up to 2 MB and requires your explicit consent before upload.</p>
                  <p className="mt-3 rounded-xl bg-mist p-3 text-sm text-slate-600">A captured or submitted selfie is not proof of identity approval.</p>
                  {status?.selfie_status === 'SUBMITTED' ? (
                    <div className="mt-5 rounded-xl border border-emerald-100 bg-emerald-50 p-4">
                      <p className="font-semibold text-emerald-900">Selfie submitted</p>
                      <p className="mt-1 text-sm text-emerald-800">The server confirms receipt. Identity approval is still pending.</p>
                    </div>
                  ) : selfie ? (
                    <div className="mt-5">
                      <img src={selfiePreview} alt="Captured selfie preview" className="aspect-video w-full max-w-md rounded-2xl bg-ink object-contain" />
                      <p className="mt-2 text-sm text-slate-500">JPEG preview · {(selfie.size / (1024 * 1024)).toFixed(2)} MB</p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <Button variant="secondary" onClick={() => setSelfie(null)} disabled={busy}>Retake selfie</Button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <video ref={selfieVideoRef} className="mt-5 aspect-video w-full max-w-md rounded-2xl bg-ink object-cover" muted playsInline aria-label="Live selfie camera preview" />
                      <div className="mt-4 flex flex-wrap gap-2">
                        <Button variant="secondary" onClick={() => startCamera('selfie')} disabled={busy || cameraActive}>
                          <Camera size={16} className="mr-2 inline" />{cameraActive && cameraMode === 'selfie' ? 'Camera active' : 'Start camera'}
                        </Button>
                        <Button onClick={captureSelfie} disabled={!cameraActive || cameraMode !== 'selfie' || busy}>Capture</Button>
                      </div>
                    </>
                  )}
                  {status?.selfie_status !== 'SUBMITTED' && (
                    <label className="mt-5 flex items-start gap-3 text-sm leading-6 text-slate-700">
                      <input type="checkbox" checked={selfieConsent} onChange={(event) => setSelfieConsent(event.target.checked)} className="mt-1 h-4 w-4" />
                      I consent to the capture and private submission of this selfie for identity verification.
                    </label>
                  )}
                  {uploadProgress && <UploadProgress label={uploadProgress.label} value={uploadProgress.value} />}
                </section>
              )}

              {step === 4 && (
                <section aria-labelledby="liveness-heading">
                  <h2 id="liveness-heading" className="text-xl font-bold text-ink">Liveness challenge</h2>
                  <p className="mt-2 text-sm leading-6 text-slate-600">A real challenge can be issued and submitted through the existing API. The configured backend provider is unavailable, so a submitted recording will not produce a genuine LIVE result.</p>
                  <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900">
                    Challenge issuance or video submission is not proof of liveness. If submitted without a provider, expect the backend to return Review required.
                  </div>
                  {!challenge || challengeExpired ? (
                    <>
                      <div className="mt-5 flex flex-wrap items-center gap-3">
                        <span className="text-sm font-semibold text-slate-600">Current backend status</span>
                        <StatusBadge value={status?.liveness_status || 'NOT_STARTED'} label={statusLabel(status?.liveness_status)} />
                      </div>
                      <Button className="mt-4" onClick={requestChallenge} disabled={busy || !verificationId}>
                        {busy ? <LoaderCircle size={16} className="mr-2 inline animate-spin" /> : <Clock3 size={16} className="mr-2 inline" />}
                        {challengeExpired ? 'Request a new challenge' : 'Request liveness challenge'}
                      </Button>
                    </>
                  ) : (
                    <div className="mt-5 rounded-2xl border border-slate-200 p-4">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <h3 className="font-bold text-ink">Challenge steps</h3>
                        <StatusBadge value={challenge.liveness_status} label={statusLabel(challenge.liveness_status)} />
                      </div>
                      <ol className="mt-3 list-inside list-decimal space-y-1 text-sm text-slate-700">
                        {challenge.steps.map((challengeStep) => <li key={challengeStep}>{challengeStep.replaceAll('_', ' ')}</li>)}
                      </ol>
                      <p className="mt-3 text-sm text-slate-600">Follow the listed actions naturally while recording the short clip. The backend, not this interface, determines the result.</p>
                      <p className="mt-2 text-xs text-slate-500">Challenge expires: {new Date(challenge.expires_at).toLocaleString()}</p>
                      {challengeExpired && <p role="alert" className="mt-2 text-sm font-semibold text-red-700">This challenge has expired. Request another before recording or submitting.</p>}
                    </div>
                  )}

                  {!challengeExpired && challenge && (
                    <>
                      <video ref={livenessVideoRef} className="mt-5 aspect-video w-full max-w-md rounded-2xl bg-ink object-cover" muted playsInline aria-label="Live liveness camera preview" />
                      <div className="mt-4 flex flex-wrap gap-2">
                        <Button variant="secondary" onClick={() => startCamera('liveness')} disabled={busy || cameraActive || isRecording}>
                          <Camera size={16} className="mr-2 inline" />Start camera
                        </Button>
                        {!isRecording ? (
                          <Button onClick={startLivenessRecording} disabled={!cameraActive || cameraMode !== 'liveness' || busy}>Start recording</Button>
                        ) : (
                          <Button onClick={stopLivenessRecording} disabled={busy} className="bg-red-700 hover:bg-red-800">Stop recording</Button>
                        )}
                      </div>
                      {livenessCapture && (
                        <div className="mt-4 rounded-xl bg-mist p-3 text-sm text-slate-700">
                          Recording ready · {(recordingSize / (1024 * 1024)).toFixed(2)} MB
                          <Button variant="secondary" className="ml-3" onClick={() => setLivenessCapture(null)} disabled={busy}>Discard and record again</Button>
                        </div>
                      )}
                      <label className="mt-5 flex items-start gap-3 text-sm leading-6 text-slate-700">
                        <input type="checkbox" checked={livenessConsent} onChange={(event) => setLivenessConsent(event.target.checked)} className="mt-1 h-4 w-4" />
                        I consent to submitting this liveness recording for assessment. I understand the provider is unavailable and the result may require review.
                      </label>
                      <Button className="mt-4" onClick={submitLivenessCapture} disabled={!livenessCapture || !livenessConsent || busy}>
                        {busy ? <LoaderCircle size={16} className="mr-2 inline animate-spin" /> : <Video size={16} className="mr-2 inline" />}
                        Submit recording
                      </Button>
                    </>
                  )}
                  {uploadProgress && <UploadProgress label={uploadProgress.label} value={uploadProgress.value} />}
                  <p className="mt-5 text-sm text-slate-500">You may continue to the final status even if no provider assessment is available. The final page will show the actual backend status.</p>
                </section>
              )}

              {step === 5 && (
                <section aria-labelledby="final-heading">
                  <div className="flex items-start gap-3">
                    <ShieldCheck className="mt-1 shrink-0 text-signal" size={26} />
                    <div>
                      <h2 id="final-heading" className="text-xl font-bold text-ink">Verification status</h2>
                      <p className="mt-2 text-sm leading-6 text-slate-600">These statuses reflect backend responses. Email ownership is separate from institutional enrollment, which remains unverified until an authoritative institution source is connected.</p>
                    </div>
                  </div>
                  <dl className="mt-6 divide-y divide-slate-100">
                    <StatusRow label="Account" value={user ? 'REGISTERED' : 'NOT_STARTED'} />
                    <StatusRow label="Institution selection" value={selectedInstitution && savedInstitutionId === institutionId ? 'SELECTED' : 'NOT_SELECTED'} />
                    <StatusRow label="Email demo state (not ownership verification)" value={emailStatus} />
                    <StatusRow label="Institution enrollment" value={enrollmentStatus} />
                    <StatusRow label="Document analysis" value={status?.document_analysis_status || documentAnalysisStatus || missingStatus} />
                    <StatusRow label="Selfie capture" value={status?.selfie_status || (status ? 'NOT_SUBMITTED' : missingStatus)} />
                    <StatusRow label="Liveness" value={status?.liveness_status || missingStatus} />
                    <StatusRow label="Liveness provider" value="PROVIDER_UNAVAILABLE" />
                    <StatusRow label="Face match" value={status?.face_match_status || missingStatus} />
                    <StatusRow label="Overall identity verification" value={status?.outcome || (error ? 'UNAVAILABLE' : 'PENDING')} />
                  </dl>
                  <div className="mt-5 rounded-xl bg-mist p-4 text-sm leading-6 text-slate-600">
                    <p>Verified is shown only when the backend returns VERIFIED. REVIEW_REQUIRED, RETRY_REQUIRED, pending, and provider-unavailable states are not successful verification.</p>
                    <p className="mt-2">Current verification reference: {verificationId ? `${verificationId.slice(0, 8)}…` : 'No document submission yet'}</p>
                  </div>
                </section>
              )}
            </div>

            <footer className="mt-8 flex flex-col gap-3 border-t border-slate-100 pt-5 sm:flex-row sm:items-center sm:justify-between">
              <div>
                {step > 1 && (
                  <Button variant="secondary" onClick={goBack} disabled={busy || isRecording}>
                    <ArrowLeft size={16} className="mr-2 inline" />Back
                  </Button>
                )}
              </div>
              {step === 1 && (
                <Button type="button" className="w-full sm:w-auto" onClick={handleInstitutionNext} disabled={loading || busy || !emailIsValid || !demoIsConfirmed || !institutionId || savedInstitutionId !== institutionId}>
                  Next: Identity Document <ArrowRight size={16} className="ml-2 inline" />
                </Button>
              )}
              {step === 2 && (
                <div className="flex flex-col items-start gap-2 sm:items-end">
                  <Button className="w-full sm:w-auto" onClick={() => setStep(3)} disabled={busy || !documentStepComplete}>
                    Next: Selfie Capture <ArrowRight size={16} className="ml-2 inline" />
                  </Button>
                  {!verificationId ? (
                    <p className="text-sm text-slate-500">Upload the identity document first to continue.</p>
                  ) : !documentStepComplete ? (
                    <p className="text-sm text-slate-500">
                      {['RETRY_REQUIRED', 'FAILED'].includes(String(currentDocumentAnalysisStatus || '').toUpperCase())
                        ? 'Document analysis needs attention. Retry analysis or upload a replacement document before continuing.'
                        : `Document analysis status: ${statusLabel(currentDocumentAnalysisStatus || 'PENDING')}. Wait for a completed backend result before continuing.`}
                    </p>
                  ) : null}
                </div>
              )}
              {step === 3 && (
                <Button className="w-full sm:w-auto" onClick={uploadSelfieAndContinue} disabled={busy || isRecording || (status?.selfie_status !== 'SUBMITTED' && (!selfie || !selfieConsent))}>
                  {busy ? <LoaderCircle size={16} className="mr-2 inline animate-spin" /> : <Upload size={16} className="mr-2 inline" />}
                  {status?.selfie_status === 'SUBMITTED' ? 'Next: Liveness' : 'Upload and continue'}
                  <ArrowRight size={16} className="ml-2 inline" />
                </Button>
              )}
              {step === 4 && (
                <Button className="w-full sm:w-auto" onClick={continueToFinalStatus} disabled={busy || isRecording || !verificationId}>
                  Next: Final Status <ArrowRight size={16} className="ml-2 inline" />
                </Button>
              )}
              {step === 5 && (
                <Button className="w-full sm:w-auto" onClick={() => navigate('/dashboard')} disabled={busy}>
                  Finish <Check size={16} className="ml-2 inline" />
                </Button>
              )}
            </footer>
          </>
        )}
      </Card>
    </main>
  )
}

function UploadProgress({ label, value }) {
  return (
    <div className="mt-4" role="status" aria-live="polite">
      <div className="flex justify-between text-xs font-semibold text-slate-600">
        <span>{label}</span>
        <span>{value}%</span>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100">
        <div className="h-full rounded-full bg-signal transition-all" style={{ width: `${value}%` }} />
      </div>
    </div>
  )
}

function StatusRow({ label, value }) {
  const normalized = String(value || 'NOT_STARTED').toUpperCase()
  const labelValue = normalized === 'REGISTERED' || normalized === 'SELECTED' || normalized === 'NOT_SELECTED'
    ? normalized.toLowerCase().replaceAll('_', ' ').replace(/^./, (letter) => letter.toUpperCase())
    : statusLabel(normalized)
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 py-3 text-sm">
      <dt className="text-slate-500">{label}</dt>
      <dd><StatusBadge value={normalized} label={labelValue} /></dd>
    </div>
  )
}
