% Generated by roxygen2: do not edit by hand
% Please edit documentation in R/PEPATACr.R
\name{tryCatchChromBins}
\alias{tryCatchChromBins}
\title{Handle warnings and errors while returning value from calcChromBinsRef()}
\usage{
tryCatchChromBins(x, y)
}
\arguments{
\item{x}{A GenomicRanges or GenomicRangesList object with query regions}

\item{y}{A character vector representing a known genome that will be used
to grab chromosome sizes with \code{getChromSizes}}
}
\description{
Handle warnings and errors while returning value from calcChromBinsRef()
}
